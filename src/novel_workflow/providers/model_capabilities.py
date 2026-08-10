from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Literal

from novel_workflow.providers.template_contract import ProviderTemplate

StructuredOutputMode = Literal["json_schema", "json_object", "prompt_only"]
SchemaTransform = Literal["none", "openai_subset"]
SamplingMode = Literal["both", "temperature", "top_p", "none"]
TokenField = Literal["max_tokens", "max_completion_tokens"]


@dataclass(frozen=True)
class EffectiveRequestPolicy:
    structured_output_mode: StructuredOutputMode
    supports_json_schema: bool
    schema_transform: SchemaTransform
    json_schema_strict: bool
    max_tokens_field: TokenField
    sampling_parameter_mode: SamplingMode
    requires_json_keyword: bool
    requires_json_example: bool
    requires_schema_definition: bool
    omit_max_tokens_in_structured: bool
    request_parameters: dict[str, object]
    extra_body_parameters: dict[str, object]
    schema_max_chars: int
    schema_max_depth: int
    schema_max_properties: int
    schema_max_enum_values: int


def resolve_request_policy(
    template: ProviderTemplate,
    *,
    model: str,
    task_name: str,
) -> EffectiveRequestPolicy:
    matching = next(
        (
            profile
            for profile in template.model_capabilities
            if fnmatchcase(model.casefold(), profile.model_pattern.casefold())
        ),
        None,
    )
    request_parameters = _merged(template.request_parameters, template.stage_request_parameters.get(task_name, {}))
    extra_body_parameters = _merged(
        template.extra_body_parameters,
        template.stage_extra_body_parameters.get(task_name, {}),
    )
    if matching is not None:
        request_parameters = _merged(
            request_parameters,
            matching.request_parameters,
            matching.stage_request_parameters.get(task_name, {}),
        )
        extra_body_parameters = _merged(
            extra_body_parameters,
            matching.extra_body_parameters,
            matching.stage_extra_body_parameters.get(task_name, {}),
        )
    return EffectiveRequestPolicy(
        structured_output_mode=(matching.structured_output_mode if matching and matching.structured_output_mode else template.structured_output_mode),
        supports_json_schema=(matching.supports_json_schema if matching and matching.supports_json_schema is not None else template.supports_json_schema),
        schema_transform=(matching.schema_transform if matching and matching.schema_transform else template.schema_transform),
        json_schema_strict=(matching.json_schema_strict if matching and matching.json_schema_strict is not None else template.json_schema_strict),
        max_tokens_field=(matching.max_tokens_field if matching and matching.max_tokens_field else template.max_tokens_field),
        sampling_parameter_mode=(matching.sampling_parameter_mode if matching and matching.sampling_parameter_mode else template.sampling_parameter_mode),
        requires_json_keyword=(matching.requires_json_keyword if matching and matching.requires_json_keyword is not None else template.requires_json_keyword),
        requires_json_example=(matching.requires_json_example if matching and matching.requires_json_example is not None else template.requires_json_example),
        requires_schema_definition=(matching.requires_schema_definition if matching and matching.requires_schema_definition is not None else template.requires_schema_definition),
        omit_max_tokens_in_structured=(matching.omit_max_tokens_in_structured if matching and matching.omit_max_tokens_in_structured is not None else template.omit_max_tokens_in_structured),
        request_parameters=request_parameters,
        extra_body_parameters=extra_body_parameters,
        schema_max_chars=template.schema_max_chars,
        schema_max_depth=template.schema_max_depth,
        schema_max_properties=template.schema_max_properties,
        schema_max_enum_values=template.schema_max_enum_values,
    )


def _merged(*values: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for value in values:
        for key, item in value.items():
            current = result.get(key)
            if isinstance(current, dict) and isinstance(item, dict):
                result[key] = _merged(current, item)
            else:
                result[key] = deepcopy(item)
    return result
