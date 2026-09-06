from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


NodeType = Literal[
    "brief",
    "cast",
    "spine",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
]

ProviderKind = Literal["openai-compatible", "openai-compatible-image"]
ProviderTemplateId = str
FieldType = Literal["text", "textarea", "number", "select", "tags", "boolean"]
QualityMode = Literal["fast", "balanced", "deep"]
QualityContractVersion = Literal["phase26-vnext"]
PricingEstimateBasis = Literal[
    "published_rates",
    "conservative_upper_bound",
    "fixed_output_estimate",
]


class ModelSettings(BaseModel):
    model: str = "gpt-4.1-mini"
    temperature: float = 0.7
    max_tokens: int = 1800
    top_p: float = 0.95
    timeout_seconds: int = 120


class InputField(BaseModel):
    key: str
    label: str
    type: FieldType = "text"
    required: bool = False
    default: Any = None
    help: str = ""
    hint: str = ""
    placeholder: str = ""
    options: list[str] = Field(default_factory=list)


class ProviderModelPricing(BaseModel):
    """One model-specific, traceable pricing declaration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    currency: Literal["USD"] = "USD"
    input_usd_per_million_tokens: float | None = Field(default=None, ge=0)
    output_usd_per_million_tokens: float | None = Field(default=None, ge=0)
    fixed_output_usd: float | None = Field(default=None, ge=0)
    source_url: str = Field(min_length=1, max_length=2_000)
    verified_at: str = Field(min_length=1, max_length=80)
    estimate_basis: PricingEstimateBasis
    estimate_basis_note: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        if not any(
            value is not None
            for value in (
                self.input_usd_per_million_tokens,
                self.output_usd_per_million_tokens,
                self.fixed_output_usd,
            )
        ):
            raise ValueError("Provider model pricing requires at least one rate")
        if not self.source_url.startswith(("https://", "http://")):
            raise ValueError("Provider pricing source URL must use HTTP(S)")
        try:
            verified = datetime.fromisoformat(self.verified_at)
        except ValueError as exc:
            raise ValueError("Provider pricing verification time must be ISO 8601") from exc
        if verified.tzinfo is None:
            raise ValueError("Provider pricing verification time must include a timezone")
        return self


class ProviderProfile(BaseModel):
    id: str
    name: str
    kind: ProviderKind = "openai-compatible"
    template_id: ProviderTemplateId = Field(default="openai-compatible-text", min_length=1)
    base_url: str = ""
    api_key_env: str = ""
    default_model: str = "gpt-4.1-mini"
    model_options: list[str] = Field(default_factory=list)
    model_supported_parameters: dict[str, list[str]] = Field(default_factory=dict)
    estimated_cost_per_output_usd: Optional[float] = Field(default=None, ge=0)
    estimated_input_cost_per_million_tokens_usd: Optional[float] = Field(
        default=None,
        ge=0,
    )
    estimated_output_cost_per_million_tokens_usd: Optional[float] = Field(
        default=None,
        ge=0,
    )
    model_pricing: dict[str, ProviderModelPricing] = Field(default_factory=dict)
    is_global_default: bool = False
    enabled: bool = True

class GenerationBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tokens: int
    description: str = ""


class PromptTemplate(BaseModel):
    id: str
    name: str
    stage_type: NodeType
    content: str
    variables: list[str] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: NodeType
    label: str
    provider_profile_id: str = "openai-compatible"
    image_provider_profile_id: str = ""
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    prompt_template_id: str = ""
    input_schema: list[InputField] = Field(default_factory=list)
    generation_budget: GenerationBudget | None = None

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str


class CanvasNodePosition(BaseModel):
    x: float
    y: float


class CanvasViewport(BaseModel):
    x: float = 0
    y: float = 0
    zoom: float = 1


class CanvasLayout(BaseModel):
    nodes: dict[str, CanvasNodePosition] = Field(default_factory=dict)
    viewport: CanvasViewport = Field(default_factory=CanvasViewport)
    crosscutting_visible: bool = True
    locked: bool = False


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    architecture_version: Literal["phase27-vnext"]
    id: str
    name: str
    version: str
    is_template: bool
    global_inputs: list[InputField] = Field(default_factory=list)
    provider_profiles: list[ProviderProfile] = Field(default_factory=list)
    prompt_templates: list[PromptTemplate] = Field(default_factory=list)
    quality_mode: QualityMode = "balanced"
    canvas_layout: CanvasLayout = Field(default_factory=CanvasLayout)
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class WorkflowDuplicateRequest(BaseModel):
    new_id: str = Field(default="", max_length=160, pattern=r"^$|^[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(default="", max_length=160)
    is_template: Optional[bool] = None
