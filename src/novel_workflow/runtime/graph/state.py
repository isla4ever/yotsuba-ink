from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.storage.narrative_run_repository import StageStatus


RunStatus = Literal[
    "created",
    "running",
    "awaiting_decision",
    "completed",
    "failed",
    "cancelled",
]


class GraphFailure(TypedDict):
    node_id: str
    code: str
    retryable: bool
    evidence_ref: NotRequired[str]
    message: NotRequired[str]


def keep_first_failure(
    current: GraphFailure | None,
    update: GraphFailure | None,
) -> GraphFailure | None:
    return current if current is not None else update


class NarrativeRunState(TypedDict, total=False):
    """Routing state only; domain content remains behind immutable references."""

    run_id: str
    project_id: str
    workflow_revision: str
    quality_mode: Literal["fast", "balanced", "deep"]
    scale_profile_ref: str
    artifact_refs: dict[StageId, str]
    candidate_artifact_refs: dict[StageId, str]
    chapter_version_refs: dict[str, str]
    chapter_attempts: dict[str, int]
    chapter_revision_directions: dict[str, str]
    context_manifest_ref: str
    active_stage_id: StageId
    active_chapter_number: int
    active_chapter_id: str
    stage_status: dict[StageId, StageStatus]
    status: RunStatus
    domain_revision: int
    stage_attempts: dict[StageId, int]
    stage_revision_directions: dict[StageId, str]
    decision_actions: dict[StageId, str]
    decision_ids: dict[StageId, str]
    pending_operation_refs: Annotated[list[str], operator.add]
    review_operation_refs: Annotated[list[str], operator.add]
    role_demand_proposals: list[dict[str, Any]]
    subject_refs: list[dict[str, str]]
    volume_boundary_proposal: dict[str, Any]
    pending_evidence_refs: list[str]
    pending_writeback_ref: str
    active_review_roles: list[dict[str, Any]]
    review_role: str
    review_required: bool
    chapter_gate_action: str
    failure: Annotated[GraphFailure | None, keep_first_failure]


def copy_stage_status(
    state: NarrativeRunState,
    stage_id: StageId,
    status: StageStatus,
) -> dict[StageId, StageStatus]:
    values = dict(state.get("stage_status") or {})
    values[stage_id] = status
    return values


def copy_stage_mapping(
    state: NarrativeRunState,
    key: Literal[
        "artifact_refs",
        "candidate_artifact_refs",
        "stage_attempts",
        "stage_revision_directions",
        "decision_actions",
        "decision_ids",
    ],
    stage_id: StageId,
    value: Any,
) -> dict[StageId, Any]:
    values = dict(state.get(key) or {})
    values[stage_id] = value
    return values


__all__ = [
    "GraphFailure",
    "NarrativeRunState",
    "RunStatus",
    "copy_stage_mapping",
    "copy_stage_status",
    "keep_first_failure",
]
