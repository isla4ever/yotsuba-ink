from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.providers.template_contract import ProviderTemplate
from novel_workflow.workflows.schemas import ProviderProfile


StructuredMode = Literal["json_schema", "json_object", "prompt_only"]


class FrozenModelCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_pattern: str = Field(min_length=1)
    structured_output_mode: StructuredMode | None = None
    supports_json_schema: bool | None = None
    schema_transform: Literal["none", "openai_subset"] | None = None
    json_schema_strict: bool | None = None
    max_tokens_field: Literal["max_tokens", "max_completion_tokens"] | None = None
    sampling_parameter_mode: Literal["both", "temperature", "top_p", "none"] | None = None
    requires_json_keyword: bool | None = None
    requires_json_example: bool | None = None
    requires_schema_definition: bool | None = None
    omit_max_tokens_in_structured: bool | None = None
    request_parameters: dict[str, object]
    extra_body_parameters: dict[str, object]
    stage_request_parameters: dict[str, dict[str, object]]
    stage_extra_body_parameters: dict[str, dict[str, object]]


class FrozenImageModelCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_pattern: str = Field(min_length=1)
    image_size_field: Literal["size", "image_size", "resolution", "aspect_ratio", "width_height"] | None = None
    image_static_parameters: dict[str, str | int | float | bool]


class FrozenProviderConfig(BaseModel):
    """Execution-critical Provider fields captured at Run creation time."""

    model_config = ConfigDict(extra="forbid")

    provider_profile_id: str = Field(min_length=1, max_length=120)
    kind: Literal["openai-compatible", "openai-compatible-image"]
    template_id: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2000)
    secret_ref: str = Field(min_length=1, max_length=240)
    model_supported_parameters: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def from_profile(cls, profile: ProviderProfile) -> "FrozenProviderConfig":
        return cls(
            provider_profile_id=profile.id,
            kind=profile.kind,
            template_id=profile.template_id,
            base_url=profile.base_url.rstrip("/"),
            secret_ref=profile.id,
            model_supported_parameters=profile.model_supported_parameters,
        )


class FrozenProviderTemplate(BaseModel):
    """Execution-only Provider template snapshot without secret environment metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    kind: Literal["openai-compatible", "openai-compatible-image"]
    supports_response_format: bool
    structured_output_mode: StructuredMode
    supports_json_schema: bool
    schema_transform: Literal["none", "openai_subset"]
    json_schema_strict: bool
    requires_json_keyword: bool
    requires_json_example: bool
    requires_schema_definition: bool
    omit_max_tokens_in_structured: bool
    empty_content_policy: Literal["standard", "documented_structured_empty"]
    assistant_prefill_mode: Literal[
        "none",
        "assistant_prefix",
        "deepseek_prefix_beta",
        "kimi_partial",
    ]
    assistant_prefill_base_url: str
    assistant_prefill_tasks: list[str]
    assistant_prefill_model_patterns: list[str]
    supports_prompt_cache_key: bool
    prompt_cache_key_header: Literal["", "x-grok-conv-id"]
    sampling_parameter_mode: Literal["both", "temperature", "top_p", "none"]
    omit_sampling_when_thinking: bool
    image_size_separator: Literal["x", ":"]
    image_size_field: Literal["size", "image_size", "resolution", "aspect_ratio", "width_height"]
    image_count_field: Literal["n", "images", "batch_size", "none"]
    image_response_field: Literal["data", "images"]
    image_endpoint_path: str
    models_endpoint_path: str
    image_static_parameters: dict[str, str | int | float | bool]
    supports_image_quality: bool
    max_retries: int = Field(ge=0, le=3)
    auth_header: Literal["authorization", "api-key"]
    max_tokens_field: Literal["max_tokens", "max_completion_tokens"]
    request_parameters: dict[str, object]
    extra_body_parameters: dict[str, object]
    stage_request_parameters: dict[str, dict[str, object]]
    stage_extra_body_parameters: dict[str, dict[str, object]]
    model_capabilities: list[FrozenModelCapability]
    image_model_capabilities: list[FrozenImageModelCapability]
    schema_max_chars: int = Field(ge=256)
    schema_max_depth: int = Field(ge=1)
    schema_max_properties: int = Field(ge=1)
    schema_max_enum_values: int = Field(ge=1)

    @classmethod
    def from_template(cls, template: ProviderTemplate) -> "FrozenProviderTemplate":
        source = template.model_dump(mode="python")
        projection = {field: source[field] for field in cls.model_fields}
        projection["model_capabilities"] = [
            {
                field: capability[field]
                for field in FrozenModelCapability.model_fields
            }
            for capability in source["model_capabilities"]
        ]
        projection["image_model_capabilities"] = [
            {
                field: capability[field]
                for field in FrozenImageModelCapability.model_fields
            }
            for capability in source["image_model_capabilities"]
        ]
        return cls(**projection)


class FrozenStructuredTask(BaseModel):
    """The exact structured-output contract accepted before a Run is created."""

    model_config = ConfigDict(extra="forbid")

    schema_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_mode: StructuredMode


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prompt_digest(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def schema_digest(schema: dict[str, Any]) -> str:
    return canonical_digest(schema)


def frozen_provider_config_digest(config: FrozenProviderConfig) -> str:
    return canonical_digest(config.model_dump(mode="json"))


def frozen_provider_template_digest(template: FrozenProviderTemplate) -> str:
    return canonical_digest(template.model_dump(mode="json"))


__all__ = [
    "FrozenStructuredTask",
    "FrozenProviderConfig",
    "FrozenProviderTemplate",
    "FrozenModelCapability",
    "FrozenImageModelCapability",
    "StructuredMode",
    "canonical_digest",
    "frozen_provider_config_digest",
    "frozen_provider_template_digest",
    "prompt_digest",
    "schema_digest",
]
