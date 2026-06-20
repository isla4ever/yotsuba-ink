from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
ProviderKind = Literal["mock", "openai-compatible", "image-mock"]
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
    model: str = "mock-novel-model"
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
    judge_model: str = "mock-novel-judge"
    dimensions: list[str] = Field(default_factory=lambda: ["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"])
    retry_on_fail: bool = False


class ProviderProfile(BaseModel):
    id: str
    name: str
    kind: ProviderKind = "mock"
    base_url: str = ""
    api_key_env: str = ""
    default_model: str = "mock-novel-model"
    model_options: list[str] = Field(default_factory=list)
    is_global_default: bool = False
    enabled: bool = True


class PromptTemplate(BaseModel):
    id: str
    name: str
    stage_type: NodeType
    content: str
    variables: list[str] = Field(default_factory=list)


class StageConfig(BaseModel):
    node_id: str
    input_schema: list[InputField] = Field(default_factory=list)
    provider_profile_id: str = "mock-text"
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    prompt_template_id: str = ""
    output_schema: dict[str, Any] = Field(default_factory=dict)
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    batch_policy: BatchPolicy = Field(default_factory=BatchPolicy)
    variant_policy: VariantPolicy = Field(default_factory=VariantPolicy)
    analysis_mode: AnalysisMode = "summary"


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    label: str
    params: dict[str, Any] = Field(default_factory=dict)
    input_refs: list[str] = Field(default_factory=list)
    output_key: str | None = None
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    provider_profile_id: str = "mock-text"
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    prompt_template_id: str = ""
    input_schema: list[InputField] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    variant_policy: VariantPolicy = Field(default_factory=VariantPolicy)


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
    global_inputs: list[InputField] = Field(default_factory=list)
    provider_profiles: list[ProviderProfile] = Field(default_factory=list)
    prompt_templates: list[PromptTemplate] = Field(default_factory=list)
    stage_configs: dict[str, StageConfig] = Field(default_factory=dict)
    batch_policy: BatchPolicy = Field(default_factory=BatchPolicy)
    quality_mode: QualityMode = "balanced"
    canvas_layout: CanvasLayout = Field(default_factory=CanvasLayout)
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class QualityEvent(BaseModel):
    node_id: str
    node_type: NodeType
    label: str
    score: float
    min_score: float
    passed: bool
    checks: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class QualityFinding(BaseModel):
    id: str
    dimension: str
    severity: QualitySeverity = "warning"
    message: str
    evidence: str = ""
    target: str = ""
    blocking: bool = False


class QualityReport(BaseModel):
    node_id: str
    node_type: NodeType
    label: str
    chapter: str = ""
    score: float = 0.0
    passed: bool = True
    mode: QualityMode = "balanced"
    findings: list[QualityFinding] = Field(default_factory=list)
    constraint_hits: list[str] = Field(default_factory=list)
    revision_required: bool = False


class RevisionDirective(BaseModel):
    id: str
    node_id: str
    chapter: str = ""
    severity: QualitySeverity = "warning"
    issue: str
    evidence: str = ""
    target: str = ""
    instruction: str
    status: RevisionStatus = "pending"
    attempts: int = 0


class ChapterContextPacket(BaseModel):
    chapter: str
    chapter_index: int
    chapter_kind: ChapterKind = "normal"
    story_brief: str = ""
    summary: str = ""
    volume_goal: str = ""
    chapter_outline: str = ""
    previous_chapter_summary: str = ""
    previous_volume_ending: str = ""
    character_state: dict[str, Any] = Field(default_factory=dict)
    open_foreshadows: list[dict[str, Any]] = Field(default_factory=list)
    world_rules: list[str] = Field(default_factory=list)


class StoryBibleState(BaseModel):
    world_rules: list[str] = Field(default_factory=list)
    character_profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    foreshadow_ledger: list[dict[str, Any]] = Field(default_factory=list)
    volumes: list[dict[str, Any]] = Field(default_factory=list)
    chapter_summaries: list[dict[str, Any]] = Field(default_factory=list)
    updated_by: str = ""


class ChapterProgressItem(BaseModel):
    volume: str
    chapter: str
    status: Literal["planned", "running", "completed", "failed"] = "planned"
    words: int = 0
    quality_score: float = 0.0
    node_id: str = ""


class CharacterNode(BaseModel):
    id: str
    name: str
    role: str
    faction: str = ""
    status: str = ""


class CharacterEdge(BaseModel):
    source: str
    target: str
    relation: str
    strength: float = 0.5


class CharacterGraph(BaseModel):
    nodes: list[CharacterNode] = Field(default_factory=list)
    edges: list[CharacterEdge] = Field(default_factory=list)
    updated_by: str = ""


class ChapterDraft(BaseModel):
    chapter: str
    volume: str = "第一卷"
    content: str = ""
    status: Literal["drafting", "completed", "selected"] = "drafting"
    words: int = 0
    variant_id: str = ""
    score: float = 0.0


class SelectedVariant(BaseModel):
    node_id: str
    chapter: str = ""
    variant_id: str
    score: float
    reason: str = ""


class RunRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    run_id: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)


class NovelRunState(BaseModel):
    run_id: str
    project_id: str
    workflow_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    wiki_refs: list[dict[str, Any]] = Field(default_factory=list)
    memory_contexts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    topology: dict[str, Any] = Field(default_factory=dict)
    current_phase: str = "planning"
    quality_reports: list[dict[str, Any]] = Field(default_factory=list)
    quality_events: list[QualityEvent] = Field(default_factory=list)
    chapter_progress: list[ChapterProgressItem] = Field(default_factory=list)
    chapter_drafts: list[ChapterDraft] = Field(default_factory=list)
    selected_variants: list[SelectedVariant] = Field(default_factory=list)
    token_estimates: dict[str, Any] = Field(default_factory=dict)
    worldbuilding_state: dict[str, Any] = Field(default_factory=dict)
    wiki_state: dict[str, Any] = Field(default_factory=dict)
    character_graph: CharacterGraph = Field(default_factory=CharacterGraph)
    cover_results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = False
    approved_artifacts: dict[str, Any] = Field(default_factory=dict)
    story_brief: dict[str, Any] = Field(default_factory=dict)
    reference_process: list[dict[str, Any]] = Field(default_factory=list)
    analysis_mode: AnalysisMode = "summary"
    story_bible: StoryBibleState = Field(default_factory=StoryBibleState)
    revision_directives: list[RevisionDirective] = Field(default_factory=list)
    chapter_context_packets: list[ChapterContextPacket] = Field(default_factory=list)
    foreshadow_ledger: list[dict[str, Any]] = Field(default_factory=list)
    continuity_state: dict[str, Any] = Field(default_factory=dict)


class ArtifactApprovalRequest(BaseModel):
    node_id: str = "info"
    output_key: str = "info_recommend"
    artifact: Any


class BriefRegenerateRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    inputs: dict[str, Any] = Field(default_factory=dict)
