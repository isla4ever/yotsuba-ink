from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


NodeType = Literal[
    "info_recommend",
    "summary",
    "outline",
    "detail_outline",
    "chapter_text",
    "cover_image",
    "export_artifact",
]

MemoryScope = Literal["project", "volume", "chapter"]
MemoryKind = Literal["worldbuilding", "topology", "outline", "chapter", "quality", "cover"]
ProviderKind = Literal["openai-compatible", "openai-compatible-image"]
ProviderTemplateId = str
FieldType = Literal["text", "textarea", "number", "select", "tags", "boolean"]
QualityMode = Literal["fast", "balanced", "deep"]
AnalysisMode = Literal["off", "summary", "enhanced"]
QualitySeverity = Literal["info", "warning", "blocking"]
RevisionStatus = Literal["pending", "applied", "failed", "skipped"]
ChapterKind = Literal["first", "normal", "volume_start", "volume_end", "finale"]


class MemoryPolicy(BaseModel):
    read: bool = True
    write: bool = True
    scope: MemoryScope = "project"
    kinds: list[MemoryKind] = Field(default_factory=list)


class ModelSettings(BaseModel):
    model: str = "gpt-4.1-mini"
    temperature: float = 0.7
    max_tokens: int = 1800
    top_p: float = 0.95
    timeout_seconds: int = 120


class FallbackTarget(BaseModel):
    provider_profile_id: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    priority: int = Field(ge=1, le=3)

    @field_validator("provider_profile_id", "model")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Fallback Provider and model are required")
        return normalized


class InputField(BaseModel):
    key: str
    label: str
    type: FieldType = "text"
    required: bool = False
    default: Any = None
    help: str = ""
    # Phase 12 A3: optional writer-facing guidance. `hint` renders as small
    # print under the label; `placeholder` fills the empty control. Both are
    # additive — absent keys keep legacy workflow JSON valid unchanged.
    hint: str = ""
    placeholder: str = ""
    options: list[str] = Field(default_factory=list)


class QualityPolicy(BaseModel):
    min_score: float = 0.8
    retry_on_fail: bool = True
    require_human_review: bool = False
    checks: list[str] = Field(default_factory=list)


class BatchPolicy(BaseModel):
    enabled: bool = False
    count: int = 1
    parallelism: int = 1


class VariantPolicy(BaseModel):
    enabled: bool = False
    candidate_count: int = 1
    judge_provider_profile_id: str = "inherit"
    judge_model: str = "gpt-4.1-mini"
    dimensions: list[str] = Field(default_factory=lambda: ["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"])
    retry_on_fail: bool = False


class ProviderProfile(BaseModel):
    id: str
    name: str
    kind: ProviderKind = "openai-compatible"
    template_id: ProviderTemplateId = Field(default="openai-compatible-text", min_length=1)
    base_url: str = ""
    api_key_env: str = ""
    default_model: str = "gpt-4.1-mini"
    model_options: list[str] = Field(default_factory=list)
    estimated_cost_per_output_usd: Optional[float] = Field(default=None, ge=0)
    is_global_default: bool = False
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_template(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("template_id"):
            return value
        migrated = dict(value)
        migrated["template_id"] = (
            "openai-compatible-image"
            if value.get("kind") == "openai-compatible-image"
            else "openai-compatible-text"
        )
        return migrated

class GenerationBudget(BaseModel):
    target_chars: int
    min_chars: int
    max_chars: int
    max_tokens: int
    description: str = ""


class PromptTemplate(BaseModel):
    id: str
    name: str
    stage_type: NodeType
    content: str
    variables: list[str] = Field(default_factory=list)


class StageConfig(BaseModel):
    node_id: str
    input_schema: list[InputField] = Field(default_factory=list)
    provider_profile_id: str = "openai-compatible"
    image_provider_profile_id: str = ""
    fallback_targets: list[FallbackTarget] = Field(default_factory=list, max_length=3)
    image_fallback_targets: list[FallbackTarget] = Field(default_factory=list, max_length=3)
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    prompt_template_id: str = ""
    output_schema: dict[str, Any] = Field(default_factory=dict)
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    batch_policy: BatchPolicy = Field(default_factory=BatchPolicy)
    variant_policy: VariantPolicy = Field(default_factory=VariantPolicy)
    analysis_mode: AnalysisMode = "summary"
    generation_budget: GenerationBudget | None = None

    @model_validator(mode="after")
    def validate_fallback_targets(self) -> "StageConfig":
        _validate_fallback_targets(self.provider_profile_id, self.fallback_targets, "text")
        _validate_fallback_targets(self.image_provider_profile_id, self.image_fallback_targets, "image")
        return self


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    label: str
    params: dict[str, Any] = Field(default_factory=dict)
    input_refs: list[str] = Field(default_factory=list)
    output_key: Optional[str] = None
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    provider_profile_id: str = "openai-compatible"
    image_provider_profile_id: str = ""
    fallback_targets: list[FallbackTarget] = Field(default_factory=list, max_length=3)
    image_fallback_targets: list[FallbackTarget] = Field(default_factory=list, max_length=3)
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    prompt_template_id: str = ""
    input_schema: list[InputField] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    variant_policy: VariantPolicy = Field(default_factory=VariantPolicy)
    generation_budget: GenerationBudget | None = None

    @model_validator(mode="after")
    def validate_fallback_targets(self) -> "WorkflowNode":
        _validate_fallback_targets(self.provider_profile_id, self.fallback_targets, "text")
        _validate_fallback_targets(self.image_provider_profile_id, self.image_fallback_targets, "image")
        return self


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
    id: str
    name: str
    version: str = "0.1.0"
    is_template: bool = False
    global_inputs: list[InputField] = Field(default_factory=list)
    provider_profiles: list[ProviderProfile] = Field(default_factory=list)
    prompt_templates: list[PromptTemplate] = Field(default_factory=list)
    stage_configs: dict[str, StageConfig] = Field(default_factory=dict)
    batch_policy: BatchPolicy = Field(default_factory=BatchPolicy)
    quality_mode: QualityMode = "balanced"
    canvas_layout: CanvasLayout = Field(default_factory=CanvasLayout)
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class WorkflowDuplicateRequest(BaseModel):
    new_id: str = Field(default="", max_length=160, pattern=r"^$|^[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(default="", max_length=160)
    is_template: Optional[bool] = None


def _validate_fallback_targets(
    primary_provider_id: str,
    targets: list[FallbackTarget],
    channel: str,
) -> None:
    provider_ids = [target.provider_profile_id for target in targets]
    priorities = [target.priority for target in targets]
    if len(provider_ids) != len(set(provider_ids)):
        raise ValueError(f"Duplicate {channel} fallback Provider")
    if len(priorities) != len(set(priorities)):
        raise ValueError(f"Duplicate {channel} fallback priority")
    if primary_provider_id and primary_provider_id in provider_ids:
        raise ValueError(f"Primary {channel} Provider cannot also be a fallback")
