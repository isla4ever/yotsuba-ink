"""Phase 32-only contracts for source-bound author collaboration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationContextPolicy,
    CollaborationPlan,
)
from novel_workflow.providers.phase32_contract import Phase32ProviderExecutionSnapshot
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


Phase32CollaborationMode = Literal["discuss", "plan", "revise"]
Phase32CollaborationThreadStatus = Literal["active", "archived", "deleted"]
Phase32CollaborationTurnStatus = Literal[
    "queued",
    "streaming",
    "completed",
    "cancelled",
    "failed",
    "contract_rejected",
]


class Phase32CollaborationScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_ref: str = Field(min_length=1, max_length=500)
    effective_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    unit_ref: str = Field(default="artifact", min_length=1, max_length=240)
    field_path: str = Field(default="", max_length=320)
    label: str = Field(default="", max_length=160)


class Phase32CollaborationThread(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    thread_id: str
    run_id: str
    project_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    artifact_kind: ArtifactKind
    scope: Phase32CollaborationScope
    title: str = Field(min_length=1, max_length=120)
    provider_execution: Phase32ProviderExecutionSnapshot
    context_policy_id: str
    status: Phase32CollaborationThreadStatus = "active"
    turn_count: int = Field(default=0, ge=0)
    has_unapplied_patch: bool = False
    created_at: str
    updated_at: str


class Phase32SelectionAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_id: str
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    source_ref: str
    unit_ref: str
    field_path: str = Field(min_length=1, max_length=320)
    field_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    selection_start: int = Field(ge=0)
    selection_end: int = Field(gt=0)
    selected_text_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_char_count: int = Field(gt=0)
    preview: str = Field(min_length=1, max_length=240)
    selected_text: str = Field(min_length=1, max_length=24_000)
    created_at: str

    @model_validator(mode="after")
    def validate_offsets(self) -> "Phase32SelectionAnchor":
        if self.selection_end <= self.selection_start:
            raise ValueError("Selection end must be after its start")
        if self.selection_end - self.selection_start != len(self.selected_text):
            raise ValueError("Selection offsets must match the selected text")
        if self.selected_char_count != len(self.selected_text):
            raise ValueError("Selection character count must match its text")
        return self


class Phase32CollaborationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str
    thread_id: str
    turn_id: str
    role: Literal["user", "assistant"]
    mode: Phase32CollaborationMode
    content: str = Field(min_length=1, max_length=80_000)
    status: Literal["complete", "partial", "cancelled", "failed"] = "complete"
    context_receipt_ref: str = ""
    patch_candidate_ref: str = ""
    plan: CollaborationPlan | None = None
    source_refs: tuple[str, ...] = ()
    created_at: str


class Phase32CollaborationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str
    client_turn_id: str
    thread_id: str
    run_id: str
    mode: Phase32CollaborationMode
    status: Phase32CollaborationTurnStatus
    user_message_ref: str
    assistant_message_ref: str = ""
    context_receipt_ref: str
    context_preview_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_operation_ref: str = ""
    patch_candidate_ref: str = ""
    selection_anchor: Phase32SelectionAnchor | None = None
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class Phase32ContextSourceReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Literal[
        "selection",
        "artifact",
        "upstream",
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


class Phase32CollaborationContextReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    thread_id: str
    turn_id: str
    run_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    stage_id: str
    artifact_kind: ArtifactKind
    source_artifact_ref: str
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    effective_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: tuple[Phase32ContextSourceReceipt, ...] = Field(min_length=1, max_length=80)
    history_message_refs: tuple[str, ...] = ()
    budget_chars: int = Field(ge=1)
    used_chars: int = Field(ge=0)
    token_estimate: int = Field(ge=0)
    provider_profile_id: str
    model: str
    receipt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: str


class Phase32CollaborationContextEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt: Phase32CollaborationContextReceipt
    material: dict[str, str]


class Phase32ProviderCollaborationDiscussResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=20_000)


class Phase32ProviderCollaborationPlanResult(Phase32ProviderCollaborationDiscussResult):
    plan: CollaborationPlan


class Phase32ProviderCollaborationPatchResult(Phase32ProviderCollaborationDiscussResult):
    replacement: str = Field(min_length=1, max_length=40_000)
    rationale: str = Field(min_length=1, max_length=4_000)


class Phase32ArtifactPatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["replace_text"] = "replace_text"
    field_path: str = Field(min_length=1, max_length=320)
    before_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    selection_anchor_id: str
    replacement: str = Field(min_length=1, max_length=40_000)
    rationale: str = Field(min_length=1, max_length=4_000)


class Phase32ArtifactPatchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    patch_id: str
    thread_id: str
    turn_id: str
    run_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    stage_id: str
    artifact_kind: ArtifactKind
    source_artifact_ref: str
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    effective_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    unit_ref: str
    operations: tuple[Phase32ArtifactPatchOperation, ...] = Field(min_length=1, max_length=8)
    context_receipt_ref: str
    provider_operation_ref: str
    status: Literal["proposed", "rejected", "stale"] = "proposed"
    created_at: str
    updated_at: str


class Phase32CollaborationStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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
        "patch.rejected",
        "patch.stale",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class CreatePhase32CollaborationThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    source_ref: str = ""
    unit_ref: str = "artifact"
    field_path: str = ""
    label: str = ""
    title: str = ""
    context_policy: CollaborationContextPolicy = Field(default_factory=CollaborationContextPolicy)


class Phase32CollaborationContextPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_turn_id: str = Field(min_length=1, max_length=160)
    mode: Phase32CollaborationMode = "discuss"
    message: str = Field(min_length=1, max_length=20_000)
    context_policy: CollaborationContextPolicy | None = None
    selection: Phase32SelectionAnchor | None = None


class CreatePhase32CollaborationTurnRequest(Phase32CollaborationContextPreviewRequest):
    preview_signature: str = Field(pattern=r"^[a-f0-9]{64}$")


class UpdatePhase32CollaborationThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["active", "archived"] | None = None


__all__ = [name for name in globals() if name.startswith("Phase32") or name.startswith("CreatePhase32")]
