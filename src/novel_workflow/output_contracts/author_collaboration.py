from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.storage.narrative_run_repository import ProviderBinding


CollaborationStageId = Literal["spine", "cast", "volumes", "detail", "text"]
CollaborationMode = Literal["discuss", "plan", "revise"]
CollaborationThreadStatus = Literal["active", "archived", "deleted"]
CollaborationTurnStatus = Literal[
    "awaiting_context",
    "queued",
    "streaming",
    "completed",
    "cancelled",
    "failed",
    "contract_rejected",
]


class CollaborationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(min_length=1, max_length=240)
    source_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_ref: str = Field(default="artifact", min_length=1, max_length=240)
    field_path: str = Field(default="", max_length=320)
    label: str = Field(default="", max_length=160)


class CollaborationThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    run_id: str
    project_id: str
    stage_id: CollaborationStageId
    scope: CollaborationScope
    title: str = Field(min_length=1, max_length=120)
    provider_binding: ProviderBinding
    context_policy_id: str
    status: CollaborationThreadStatus = "active"
    turn_count: int = Field(default=0, ge=0)
    has_unapplied_patch: bool = False
    created_at: str
    updated_at: str


class SelectionAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    stage_id: CollaborationStageId
    source_ref: str
    unit_ref: str
    field_path: str = Field(min_length=1, max_length=320)
    field_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_start: int = Field(ge=0)
    selection_end: int = Field(gt=0)
    selected_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_char_count: int = Field(gt=0)
    preview: str = Field(min_length=1, max_length=240)
    selected_text: str = Field(min_length=1, max_length=24_000)
    created_at: str

    @model_validator(mode="after")
    def validate_offsets(self) -> "SelectionAnchor":
        if self.selection_end <= self.selection_start:
            raise ValueError("Selection end must be after its start")
        if self.selection_end - self.selection_start != len(self.selected_text):
            raise ValueError("Selection offsets must match the selected text")
        if self.selected_char_count != len(self.selected_text):
            raise ValueError("Selection character count must match its text")
        return self


class CollaborationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    thread_id: str
    turn_id: str
    role: Literal["user", "assistant"]
    mode: CollaborationMode
    content: str = Field(min_length=1, max_length=80_000)
    status: Literal["complete", "partial", "cancelled", "failed"] = "complete"
    context_receipt_ref: str = ""
    patch_candidate_ref: str = ""
    plan: CollaborationPlan | None = None
    source_refs: list[str] = Field(default_factory=list, max_length=40)
    created_at: str


class CollaborationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str
    client_turn_id: str
    thread_id: str
    run_id: str
    mode: CollaborationMode
    status: CollaborationTurnStatus
    user_message_ref: str
    assistant_message_ref: str = ""
    context_receipt_ref: str
    context_preview_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_operation_ref: str = ""
    patch_candidate_ref: str = ""
    selection_anchor: SelectionAnchor | None = None
    attempt: int = Field(default=1, ge=1)
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class ContextSourceReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "selection",
        "artifact",
        "upstream",
        "characters",
        "continuity",
        "canon_wiki",
        "foreshadow",
        "knowledge",
        "craft",
        "author_preferences",
        "history",
    ]
    source_ref: str
    scope_ref: str
    source_version: str
    reason: str = Field(min_length=1, max_length=240)
    char_count: int = Field(ge=0)
    token_estimate: int = Field(ge=0)
    disposition: Literal["required", "optional", "omitted"]
    label: str = Field(min_length=1, max_length=160)


class CollaborationContextPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str = "collaboration-default-v1"
    version: int = Field(default=1, ge=1)
    max_input_chars: int = Field(default=24_000, ge=4_000, le=120_000)
    max_history_turns: int = Field(default=8, ge=0, le=40)
    include_author_preferences: bool = True
    include_craft_mechanisms: bool = True
    include_knowledge: bool = False
    include_canon_wiki: bool = True
    include_foreshadow: bool = True
    author_preferences: str = Field(default="", max_length=4_000)
    craft_mechanisms: list[str] = Field(default_factory=list, max_length=12)
    source_pack_refs: list[str] = Field(default_factory=list, max_length=20)


class CollaborationTurnContextReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    thread_id: str
    turn_id: str
    source_artifact_ref: str
    sources: list[ContextSourceReceipt] = Field(min_length=1, max_length=80)
    history_message_refs: list[str] = Field(default_factory=list, max_length=80)
    budget_chars: int = Field(ge=1)
    used_chars: int = Field(ge=0)
    token_estimate: int = Field(ge=0)
    provider_profile_id: str
    model: str
    receipt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str


class CollaborationContextEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt: CollaborationTurnContextReceipt
    material: dict[str, str]


class CollaborationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=1200)
    findings: list[str] = Field(min_length=1, max_length=12)
    steps: list[str] = Field(min_length=1, max_length=12)
    impacts: list[str] = Field(default_factory=list, max_length=12)
    risks: list[str] = Field(default_factory=list, max_length=12)
    questions: list[str] = Field(default_factory=list, max_length=8)


class ProviderCollaborationPlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=20_000)
    plan: CollaborationPlan


class ProviderCollaborationPatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=20_000)
    replacement: str = Field(min_length=1, max_length=40_000)
    rationale: str = Field(min_length=1, max_length=4_000)


class ArtifactPatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["replace_text"] = "replace_text"
    field_path: str = Field(min_length=1, max_length=320)
    before_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_anchor_id: str = ""
    replacement: str = Field(min_length=1, max_length=40_000)
    rationale: str = Field(min_length=1, max_length=4_000)


class ArtifactPatchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_id: str
    thread_id: str
    turn_id: str
    run_id: str
    stage_id: CollaborationStageId
    source_ref: str
    source_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_ref: str
    operations: list[ArtifactPatchOperation] = Field(min_length=1, max_length=8)
    context_receipt_ref: str
    provider_operation_ref: str
    status: Literal["proposed", "accepted", "rejected", "stale"] = "proposed"
    writeback_ref: str = ""
    created_at: str
    updated_at: str


class CollaborationStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    event_id: str
    thread_id: str
    turn_id: str = ""
    type: Literal[
        "thread.created",
        "thread.updated",
        "turn.started",
        "context.frozen",
        "turn.streaming",
        "turn.completed",
        "turn.cancelled",
        "turn.failed",
        "patch.ready",
        "patch.accepted",
        "patch.rejected",
        "patch.stale",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class CreateCollaborationThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: CollaborationStageId
    source_ref: str = ""
    unit_ref: str = "artifact"
    field_path: str = ""
    label: str = ""
    title: str = ""
    context_policy: CollaborationContextPolicy = Field(
        default_factory=CollaborationContextPolicy
    )


class CollaborationContextPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_turn_id: str = Field(min_length=1, max_length=160)
    mode: CollaborationMode = "discuss"
    message: str = Field(min_length=1, max_length=20_000)
    context_policy: CollaborationContextPolicy | None = None
    selection: SelectionAnchor | None = None


class CreateCollaborationTurnRequest(CollaborationContextPreviewRequest):
    preview_signature: str = Field(pattern=r"^[0-9a-f]{64}$")


class UpdateCollaborationThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["active", "archived"] | None = None


class CollaborationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_mode: CollaborationMode = "discuss"
    default_provider_profile_id: str = ""
    default_model: str = ""
    context_policy: CollaborationContextPolicy = Field(
        default_factory=CollaborationContextPolicy
    )
    history_retention_days: int = Field(default=180, ge=7, le=3650)


class CollaborationProviderCapability(BaseModel):
    """Sanitized collaboration capability projected from one text Provider."""

    model_config = ConfigDict(extra="forbid")

    provider_profile_id: str
    provider_name: str
    model: str
    supports_multi_turn: bool
    supports_streaming: bool
    supports_structured_patch: bool
    max_context_tokens: int | None = Field(default=None, ge=1)
    capability_checked_at: str
    capability_source: Literal["discovered", "tested", "manual"]
    ready: bool
    issue_codes: list[str] = Field(default_factory=list, max_length=20)


class CollaborationSettingsEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: CollaborationSettings
    capabilities: list[CollaborationProviderCapability] = Field(default_factory=list)


__all__ = [
    "ArtifactPatchCandidate",
    "ArtifactPatchOperation",
    "CollaborationContextEnvelope",
    "CollaborationContextPolicy",
    "CollaborationContextPreviewRequest",
    "CollaborationMessage",
    "CollaborationMode",
    "CollaborationPlan",
    "CollaborationScope",
    "CollaborationSettings",
    "CollaborationSettingsEnvelope",
    "CollaborationProviderCapability",
    "CollaborationStageId",
    "CollaborationStreamEvent",
    "CollaborationThread",
    "CollaborationTurn",
    "CollaborationTurnContextReceipt",
    "ContextSourceReceipt",
    "CreateCollaborationThreadRequest",
    "CreateCollaborationTurnRequest",
    "ProviderCollaborationPatchResult",
    "ProviderCollaborationPlanResult",
    "SelectionAnchor",
    "UpdateCollaborationThreadRequest",
]
