from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from novel_workflow.providers.model_capabilities import EffectiveRequestPolicy
from novel_workflow.providers.errors import ProviderResponseError

_REMOVED_CONSTRAINTS = {
    "default",
    "examples",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
}
_ALLOWED_KEYWORDS = {
    "$defs",
    "$ref",
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "anyOf",
    "description",
    "title",
}


@dataclass(frozen=True)
class StructuredFormatDecision:
    response_format: dict[str, Any] | None
    effective_mode: str
    rejection_reason: str = ""


def structured_format_decision(
    policy: EffectiveRequestPolicy,
    *,
    task_name: str,
    schema: dict[str, Any],
) -> StructuredFormatDecision:
    if policy.structured_output_mode == "prompt_only":
        return StructuredFormatDecision(None, "prompt_only")
    if policy.structured_output_mode != "json_schema" or not policy.supports_json_schema:
        return StructuredFormatDecision({"type": "json_object"}, "json_object")
    candidate = copy.deepcopy(schema)
    if policy.schema_transform == "openai_subset":
        candidate = _normalize_openai_subset(candidate)
    reason = _schema_incompatibility(candidate, policy=policy)
    if reason:
        raise ProviderResponseError(
            "strict_schema_unsupported",
            f"Selected Provider cannot accept the frozen structured schema: {reason}",
        )
    return StructuredFormatDecision(
        {
            "type": "json_schema",
            "json_schema": {
                "name": _schema_name(task_name),
                "strict": policy.json_schema_strict,
                "schema": candidate,
            },
        },
        "json_schema",
    )


def schema_example(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"result": "string"}
    value = _example_value(schema, root=schema, depth=0)
    return value if isinstance(value, dict) else {"result": value}


def _normalize_openai_subset(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_openai_subset(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: _normalize_openai_subset(item)
        for key, item in value.items()
        if key not in _REMOVED_CONSTRAINTS
    }
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        normalized["properties"] = properties
        normalized["required"] = list(properties)
        normalized["additionalProperties"] = False
        normalized.setdefault("type", "object")
    elif normalized.get("type") == "object":
        normalized["properties"] = {}
        normalized["required"] = []
        normalized["additionalProperties"] = False
    return normalized


def _schema_incompatibility(schema: dict[str, Any], *, policy: EffectiveRequestPolicy) -> str:
    if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
        return "root_must_be_object"
    invalid_shape = _invalid_schema_shape(schema)
    if invalid_shape:
        return invalid_shape
    unknown = _unknown_keywords(schema)
    if unknown:
        return f"unsupported_keyword:{unknown[0]}"
    if _property_count(schema) > policy.schema_max_properties:
        return "property_limit_exceeded"
    if _enum_value_count(schema) > policy.schema_max_enum_values:
        return "enum_value_limit_exceeded"
    if _nesting_depth(schema) > policy.schema_max_depth:
        return "nesting_limit_exceeded"
    if len(json.dumps(schema, ensure_ascii=False, separators=(",", ":"))) > policy.schema_max_chars:
        return "schema_size_limit_exceeded"
    return ""


def _invalid_schema_shape(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean_schema_not_supported"
    if not isinstance(value, dict):
        return ""
    enum = value.get("enum")
    if isinstance(enum, list) and not enum:
        return "empty_enum_not_supported"
    any_of = value.get("anyOf")
    if isinstance(any_of, list) and not any_of:
        return "empty_any_of_not_supported"
    reference = value.get("$ref")
    if isinstance(reference, str) and not reference.startswith("#/$defs/"):
        return "external_reference_not_supported"
    for container_key in ("properties", "$defs"):
        container = value.get(container_key)
        if isinstance(container, dict):
            for item in container.values():
                reason = _invalid_schema_shape(item)
                if reason:
                    return reason
    items = value.get("items")
    if isinstance(items, (dict, bool)):
        reason = _invalid_schema_shape(items)
        if reason:
            return reason
    if isinstance(any_of, list):
        for item in any_of:
            reason = _invalid_schema_shape(item)
            if reason:
                return reason
    return ""


def _unknown_keywords(value: Any, *, in_properties: bool = False) -> list[str]:
    if isinstance(value, list):
        return [item for child in value for item in _unknown_keywords(child)]
    if not isinstance(value, dict):
        return []
    unknown: list[str] = []
    for key, item in value.items():
        if not in_properties and key not in _ALLOWED_KEYWORDS:
            unknown.append(key)
        unknown.extend(_unknown_keywords(item, in_properties=key in {"properties", "$defs"}))
    return unknown


def _property_count(value: Any) -> int:
    if isinstance(value, list):
        return sum(_property_count(item) for item in value)
    if not isinstance(value, dict):
        return 0
    own = len(value.get("properties", {})) if isinstance(value.get("properties"), dict) else 0
    return own + sum(_property_count(item) for item in value.values())


def _enum_value_count(value: Any) -> int:
    if isinstance(value, list):
        return sum(_enum_value_count(item) for item in value)
    if not isinstance(value, dict):
        return 0
    own = len(value.get("enum", [])) if isinstance(value.get("enum"), list) else 0
    return own + sum(_enum_value_count(item) for item in value.values())


def _nesting_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, list):
        return max((_nesting_depth(item, depth) for item in value), default=depth)
    if not isinstance(value, dict):
        return depth
    schema_type = value.get("type")
    next_depth = depth + 1 if isinstance(schema_type, str) and schema_type in {"object", "array"} else depth
    return max([next_depth, *(_nesting_depth(item, next_depth) for item in value.values())])


def _example_value(schema: dict[str, Any], *, root: dict[str, Any], depth: int) -> Any:
    if depth > 4:
        return "value"
    reference = schema.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/$defs/"):
        target = root.get("$defs", {}).get(reference.rsplit("/", 1)[-1])
        if isinstance(target, dict):
            return _example_value(target, root=root, depth=depth + 1)
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        if not any_of:
            return "value"
        option = next((item for item in any_of if isinstance(item, dict) and item.get("type") != "null"), any_of[0])
        return _example_value(option, root=root, depth=depth + 1) if isinstance(option, dict) else "value"
    value_type = schema.get("type")
    if value_type == "object" or isinstance(schema.get("properties"), dict):
        properties = schema.get("properties", {})
        return {
            key: _example_value(item, root=root, depth=depth + 1)
            for key, item in list(properties.items())[:24]
            if isinstance(item, dict)
        }
    if value_type == "array":
        item = schema.get("items")
        return [_example_value(item, root=root, depth=depth + 1)] if isinstance(item, dict) else []
    if value_type == "integer":
        return 1
    if value_type == "number":
        return 1.0
    if value_type == "boolean":
        return True
    return "string"


def _schema_name(task_name: str) -> str:
    normalized = "".join(character if character.isalnum() or character in "_-" else "_" for character in task_name)
    return (normalized.strip("_-") or "stage_artifact")[:64]
