from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StructuredParseDiagnostic:
    """Safe shape-only evidence for a structured provider response.

    The diagnostic deliberately excludes response text.  It is persisted in
    run events so a failed call can be investigated without copying prose,
    user material, or provider secrets into the run snapshot.
    """

    response_chars: int
    response_sha256: str
    candidate_count: int
    balanced_object_count: int
    parsed_object_count: int
    schema_match_count: int
    top_level_types: tuple[str, ...]
    object_keys: tuple[tuple[str, ...], ...]
    selection: str
    repairs_applied: tuple[str, ...] = ()
    parse_error_codes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "response_chars": self.response_chars,
            "response_sha256": self.response_sha256,
            "candidate_count": self.candidate_count,
            "balanced_object_count": self.balanced_object_count,
            "parsed_object_count": self.parsed_object_count,
            "schema_match_count": self.schema_match_count,
            "top_level_types": list(self.top_level_types),
            "object_keys": [list(keys) for keys in self.object_keys],
            "selection": self.selection,
            "repairs_applied": list(self.repairs_applied),
            "parse_error_codes": list(self.parse_error_codes),
        }


@dataclass(frozen=True)
class StructuredParseResult:
    value: dict[str, Any] | None
    diagnostic: StructuredParseDiagnostic


def parse_exact_json_object_result(
    text: str,
    *,
    schema: dict[str, Any] | None = None,
) -> StructuredParseResult:
    """Parse one complete JSON object without extraction or syntax repair."""

    stripped = text.strip()
    parsed: Any | None = None
    parse_error_codes: tuple[str, ...] = ()
    if stripped:
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as error:
            parse_error_codes = (_json_error_code(error),)

    selected = parsed if isinstance(parsed, dict) else None
    is_schema_match = selected is not None and _matches_schema(selected, schema)
    if selected is not None:
        selection = "exact_object"
    elif parsed is not None:
        selection = "top_level_not_object"
    else:
        selection = "invalid_json" if stripped else "empty_response"
    diagnostic = StructuredParseDiagnostic(
        response_chars=len(text),
        response_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        candidate_count=1 if stripped else 0,
        balanced_object_count=0,
        parsed_object_count=1 if selected is not None else 0,
        schema_match_count=1 if is_schema_match else 0,
        top_level_types=(_json_type(parsed),) if parsed is not None else (),
        object_keys=(
            tuple(sorted(_safe_key(key) for key in selected.keys())[:32]),
        ) if selected is not None else (),
        selection=selection,
        parse_error_codes=parse_error_codes,
    )
    return StructuredParseResult(selected, diagnostic)


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _safe_key(value: Any) -> str:
    key = str(value)
    if re.search(
        r"(?:api[_-]?key|access[_-]?token|authorization|password|private[_-]?key|secret)",
        key,
        re.IGNORECASE,
    ):
        return "[redacted-key]"
    return key[:80]


def _matches_schema(value: dict[str, Any], schema: dict[str, Any] | None) -> bool:
    """Apply the small, deterministic subset needed to select one object.

    Full artifact validation remains the responsibility of output-contract
    validation.  Here we only need enough schema awareness to distinguish a
    final artifact from a model's intermediate example or reasoning object.
    """

    if not isinstance(schema, dict):
        return False
    required = schema.get("required")
    if isinstance(required, list) and any(key not in value for key in required):
        return False
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return True
    for key, definition in properties.items():
        if key not in value or not isinstance(definition, dict):
            continue
        expected = definition.get("type")
        if expected is None:
            continue
        allowed = expected if isinstance(expected, list) else [expected]
        actual = _json_type(value[key])
        if actual not in allowed and not (actual == "integer" and "number" in allowed):
            return False
    return True


def _json_error_code(error: json.JSONDecodeError) -> str:
    message = error.msg.casefold()
    if "control character" in message:
        return "unescaped_control_character"
    if "invalid \\escape" in message:
        return "invalid_escape"
    if "unterminated string" in message:
        return "unterminated_string"
    if "property name enclosed in double quotes" in message:
        return "missing_or_trailing_comma"
    return "json_decode_error"
