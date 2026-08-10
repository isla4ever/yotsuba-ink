from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from novel_workflow.workflows.schemas import ProviderKind


class ModelCapabilityProfile(BaseModel):
    model_pattern: str = Field(min_length=1)
    capability_docs: list[str] = Field(default_factory=list)
    evidence_status: Literal["verified", "conservative", "experimental"] = "verified"
    evidence_note: str = ""
    structured_output_mode: Literal["json_schema", "json_object", "prompt_only"] | None = None
    supports_json_schema: bool | None = None
    schema_transform: Literal["none", "openai_subset"] | None = None
    json_schema_strict: bool | None = None
    max_tokens_field: Literal["max_tokens", "max_completion_tokens"] | None = None
    sampling_parameter_mode: Literal["both", "temperature", "top_p", "none"] | None = None
    requires_json_keyword: bool | None = None
    requires_json_example: bool | None = None
    requires_schema_definition: bool | None = None
    omit_max_tokens_in_structured: bool | None = None
    request_parameters: dict[str, object] = Field(default_factory=dict)
    extra_body_parameters: dict[str, object] = Field(default_factory=dict)
    stage_request_parameters: dict[str, dict[str, object]] = Field(default_factory=dict)
    stage_extra_body_parameters: dict[str, dict[str, object]] = Field(default_factory=dict)


class ImageModelCapabilityProfile(BaseModel):
    model_pattern: str = Field(min_length=1)
    capability_docs: list[str] = Field(default_factory=list)
    evidence_status: Literal["verified", "conservative", "experimental"] = "verified"
    evidence_note: str = ""
    image_size_field: Literal["size", "image_size", "resolution", "aspect_ratio", "width_height"] | None = None
    image_static_parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ProviderTemplate(BaseModel):
    id: str = Field(min_length=1)
    label: str
    kind: ProviderKind
    base_url: str
    default_model: str
    model_options: list[str] = Field(default_factory=list)
    api_key_env: str
    docs_url: str
    capability_docs: list[str] = Field(default_factory=list)
    integration_tier: Literal["official", "compatibility", "gateway", "custom"] = "official"
    description: str = ""
    supports_response_format: bool = True
    structured_output_mode: Literal["json_schema", "json_object", "prompt_only"] = "json_object"
    supports_json_schema: bool = False
    schema_transform: Literal["none", "openai_subset"] = "none"
    json_schema_strict: bool = False
    requires_json_keyword: bool = False
    requires_json_example: bool = False
    requires_schema_definition: bool = False
    omit_max_tokens_in_structured: bool = False
    empty_content_policy: Literal["standard", "documented_structured_empty"] = "standard"
    assistant_prefill_mode: Literal[
        "none",
        "assistant_prefix",
        "deepseek_prefix_beta",
        "kimi_partial",
    ] = "none"
    assistant_prefill_base_url: str = ""
    assistant_prefill_tasks: list[str] = Field(default_factory=list)
    assistant_prefill_model_patterns: list[str] = Field(default_factory=list)
    supports_prompt_cache_key: bool = False
    prompt_cache_key_header: Literal["", "x-grok-conv-id"] = ""
    sampling_parameter_mode: Literal["both", "temperature", "top_p", "none"] = "both"
    omit_sampling_when_thinking: bool = False
    thinking_parameter: str = ""
    structured_output_notes: str = ""
    image_size_separator: Literal["x", ":"] = "x"
    image_size_field: Literal["size", "image_size", "resolution", "aspect_ratio", "width_height"] = "size"
    image_count_field: Literal["n", "images", "batch_size", "none"] = "n"
    image_response_field: Literal["data", "images"] = "data"
    image_endpoint_path: str = "/images/generations"
    models_endpoint_path: str = "/models"
    models_auth_header: Literal[
        "inherit",
        "authorization",
        "api-key",
        "x-portkey-api-key",
    ] = "inherit"
    models_query_parameters: dict[str, str] = Field(default_factory=dict)
    discovers_model_parameters: bool = False
    required_model_parameter_any_of: list[str] = Field(default_factory=list)
    image_static_parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    supports_image_quality: bool = True
    max_retries: int = Field(default=0, ge=0, le=3)
    auth_header: Literal["authorization", "api-key"] = "authorization"
    max_tokens_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    request_parameters: dict[str, object] = Field(default_factory=dict)
    extra_body_parameters: dict[str, object] = Field(default_factory=dict)
    stage_request_parameters: dict[str, dict[str, object]] = Field(default_factory=dict)
    stage_extra_body_parameters: dict[str, dict[str, object]] = Field(default_factory=dict)
    model_capabilities: list[ModelCapabilityProfile] = Field(default_factory=list)
    image_model_capabilities: list[ImageModelCapabilityProfile] = Field(default_factory=list)
    schema_max_chars: int = Field(default=15000, ge=256)
    schema_max_depth: int = Field(default=5, ge=1)
    schema_max_properties: int = Field(default=100, ge=1)
    schema_max_enum_values: int = Field(default=10000, ge=1)
    execution_allowed: bool = True
    execution_policy_note: str = ""
    workflow_execution_allowed: bool = True
    workflow_execution_policy_note: str = ""

    @model_validator(mode="after")
    def include_primary_capability_doc(self) -> "ProviderTemplate":
        if self.docs_url and self.docs_url not in self.capability_docs:
            self.capability_docs.insert(0, self.docs_url)
        return self
