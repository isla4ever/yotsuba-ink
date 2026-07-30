from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from novel_workflow.workflows.definition_schemas import (
    AnalysisMode,
    ChapterKind,
    NodeType,
    QualityMode,
    QualitySeverity,
    RevisionStatus,
)

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
    volume_title: str = ""
    volume_chapter_range: str = ""
    next_volume_goal: str = ""
    chapter_outline: str = ""
    previous_chapter_summary: str = ""
    previous_volume_ending: str = ""
    transition_directive: str = ""
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
    tension_track: list[dict[str, Any]] = Field(default_factory=list)
    updated_by: str = ""


class ChapterProgressItem(BaseModel):
    volume: str
    chapter: str
    status: Literal["planned", "running", "completed", "failed"] = "planned"
    words: int = 0
    quality_score: float = 0.0
    node_id: str = ""


CharacterTier = Literal["protagonist", "major", "supporting", "minor", "npc"]
RelationKind = Literal["kinship", "romance", "ally", "rival", "superior", "trade", "secret", "other"]
RelationPolarity = Literal["positive", "negative", "complex", "neutral"]
FactionStance = Literal["protagonist_side", "antagonist_side", "neutral", "hidden"]


class FactionInfo(BaseModel):
    id: str
    name: str
    stance: FactionStance = "neutral"
    description: str = ""
    first_appearance_stage: str = ""


class CharacterNode(BaseModel):
    id: str
    name: str
    role: str
    tier: CharacterTier = "supporting"
    faction: str = ""
    faction_id: str = ""
    status: str = ""
    first_appearance_stage: str = ""
    first_appearance_chapter: str = ""
    avatar_seed: str = ""
    voice_ref: str = ""


class CharacterEdge(BaseModel):
    source: str
    target: str
    relation: str
    kind: RelationKind = "other"
    polarity: RelationPolarity = "neutral"
    strength: float = 0.5
    valid_from_stage: str = ""
    valid_from_chapter: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)


class CharacterGraph(BaseModel):
    nodes: list[CharacterNode] = Field(default_factory=list)
    edges: list[CharacterEdge] = Field(default_factory=list)
    factions: list[FactionInfo] = Field(default_factory=list)
    updated_by: str = ""


class ChapterDraft(BaseModel):
    chapter: str
    volume: str = "第一卷"
    content: str = ""
    status: Literal["drafting", "completed", "selected"] = "drafting"
    words: int = 0
    variant_id: str = ""
    score: float = 0.0
    artifact: dict[str, Any] = Field(default_factory=dict)


class SelectedVariant(BaseModel):
    node_id: str
    chapter: str = ""
    variant_id: str
    score: float
    reason: str = ""


class RunRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    run_id: Optional[str] = None
    project_id: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)


class ExportPackageMetadata(BaseModel):
    title: str = Field(default="", max_length=200)
    author: str = Field(default="", max_length=160)
    version_note: str = Field(default="", max_length=500)
    bundle_name: str = Field(default="", max_length=160)


class ExportPackageRequest(BaseModel):
    format: Literal["md", "json", "zip"] = "md"
    chapter_ids: list[str] = Field(default_factory=list)
    metadata: ExportPackageMetadata = Field(default_factory=ExportPackageMetadata)
    request_id: str = Field(default="", max_length=160)


class NovelRunState(BaseModel):
    run_id: str
    project_id: str
    workflow_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    execution_mode: Literal["live"] = "live"
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
    stage_usage_summaries: dict[str, dict[str, Any]] = Field(default_factory=dict)
    stage_display_artifacts: dict[str, Any] = Field(default_factory=dict)
    runtime_phase: str = "idle_config"
    run_has_started: bool = False
    mode_locked: bool = False
    stage_confirmation_state: dict[str, Any] = Field(default_factory=dict)
    draft_regeneration_state: dict[str, Any] = Field(default_factory=dict)
    cover_asset_state: dict[str, Any] = Field(default_factory=dict)
    parallel_delivery_state: dict[str, Any] = Field(default_factory=dict)
    chapter_revision_state: dict[str, Any] = Field(default_factory=dict)
    chapter_review_state: dict[str, Any] = Field(default_factory=dict)
    model_review_state: dict[str, Any] = Field(default_factory=dict)
    recovery_state: dict[str, Any] = Field(default_factory=dict)
    budget_state: dict[str, Any] = Field(default_factory=dict)
    canon_facts: list[dict[str, Any]] = Field(default_factory=list)
    canon_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    candidate_review_state: dict[str, Any] = Field(default_factory=dict)
    variant_compare_state: dict[str, Any] = Field(default_factory=dict)
    settlement_transition: dict[str, Any] = Field(default_factory=dict)
    completed_stage_ids: list[str] = Field(default_factory=list)
    current_stage_id: str = ""
    current_stage_label: str = ""
    current_stage_type: str = ""
    current_checkpoint_stage_id: str = ""
    pending_export_return: bool = False
    run_completed_at: str = ""


class ArtifactApprovalRequest(BaseModel):
    node_id: str = "info"
    output_key: str = "info_recommend"
    artifact: Any


class BriefRegenerateRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    inputs: dict[str, Any] = Field(default_factory=dict)


class DraftRegenerateRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str
    direction: str
    candidate_count: int = 3
    request_id: str = Field(default="", max_length=120)


class DraftCandidateSelectRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str
    section: str


class ChapterSelectionRevisionRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str = "text"
    chapter_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    selected_text: str = Field(min_length=1, max_length=6000)
    operation: Literal["rewrite", "expand", "compress", "restyle"]
    direction: str = Field(default="", max_length=500)
    base_version: int = Field(ge=0)
    base_signature: str = Field(min_length=64, max_length=64)
    persisted_signature: str = Field(min_length=64, max_length=64)
    base_chapter: dict[str, Any]
    request_id: str = Field(min_length=8, max_length=120)


class ChapterSelectionRevisionApplyRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str = "text"
    request_id: str = Field(min_length=8, max_length=120)
    candidate_signature: str = Field(min_length=64, max_length=64)


class ChapterVersionRestoreRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str = "text"
    chapter_id: str
    version_id: str = Field(min_length=1, max_length=160)
    base_version: int = Field(ge=0)
    base_signature: str = Field(min_length=64, max_length=64)
    persisted_signature: str = Field(min_length=64, max_length=64)
    base_chapter: dict[str, Any]
    request_id: str = Field(min_length=8, max_length=120)


class ChapterSummarySyncRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str = "text"
    chapter_id: str
    summary: str = Field(min_length=1, max_length=6000)
    base_version: int = Field(ge=0)
    base_signature: str = Field(min_length=64, max_length=64)
    persisted_signature: str = Field(min_length=64, max_length=64)
    base_chapter: dict[str, Any]
    request_id: str = Field(min_length=8, max_length=120)


class ChapterWritebackProposalDecisionRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"
    node_id: str = "text"
    chapter_id: str
    proposal_id: str = Field(min_length=1, max_length=180)
    proposal_signature: str = Field(min_length=64, max_length=64)
    decision: Literal["accepted", "rejected"]
    base_version: int = Field(ge=0)
    base_signature: str = Field(min_length=64, max_length=64)
    request_id: str = Field(min_length=8, max_length=120)
    conflict_resolutions: dict[str, Literal["keep_existing", "replace_existing"]] = Field(default_factory=dict)
