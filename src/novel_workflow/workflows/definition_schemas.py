from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
