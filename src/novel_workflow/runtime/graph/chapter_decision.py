from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from langgraph.types import interrupt

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact
from novel_workflow.quality.decision_contract import (
    QualityDecision,
    quality_revision_direction,
)
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.chapter_store import ChapterRecord, ChapterStore
from novel_workflow.storage.event_projection import EventProjection


ChapterDecisionAction = Literal["accept", "regenerate", "cancel"]
MAX_CANDIDATE_REGENERATIONS = 1


def request_chapter_decision(
    executor: StageExecutor,
    state: NarrativeRunState,
    *,
    quality_decision: QualityDecision,
    review_status: dict[str, Any],
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    candidate_ref = (state.get("chapter_version_refs") or {})[chapter_id]
    decision_id = f"{run_id}:{chapter_id}:{candidate_ref}:author-decision"
    regeneration_count = _chapter_regeneration_count(executor, run_id, chapter_id)
    quality_decision = quality_decision.model_copy(
        update={"regeneration_used": regeneration_count}
    )
    recommended_direction = (
        quality_decision.regeneration_recommendation.direction
        if quality_decision.regeneration_recommendation is not None
        else ""
    )
    allowed_actions = quality_decision.allowed_actions()
    payload = {
        "type": "chapter_author_decision",
        "decision_id": decision_id,
        "thread_id": run_id,
        "node_id": "text.author_decision",
        "chapter_id": chapter_id,
        "artifact_ref": candidate_ref,
        "domain_revision": state.get("domain_revision", 0),
        "allowed_actions": allowed_actions,
        "regeneration_limit": MAX_CANDIDATE_REGENERATIONS,
        "regeneration_used": regeneration_count,
        "quality_decision": quality_decision.model_dump(mode="json"),
        "review_status": review_status,
    }
    exhausted_hard_blocker = bool(quality_decision.contract_blockers) and (
        "regenerate" not in allowed_actions
    )
    if state.get("quality_mode") == "fast" and not exhausted_hard_blocker:
        if quality_decision.contract_blockers:
            action = "regenerate"
            value = {"direction": recommended_direction}
        else:
            action = "accept"
            value = {}
    else:
        executor.events.append(
            run_id,
            event_id=f"{decision_id}:required",
            type="decision.required",
            stage_id="text",
            node_id="text.author_decision",
            chapter_id=chapter_id,
            status="awaiting_decision",
            payload=payload,
        )
        value = interrupt(payload)
        action = _validate_resume(
            value,
            decision_id,
            int(state.get("domain_revision") or 0),
            allowed_actions,
        )

    update: dict[str, Any] = {"chapter_gate_action": action}
    if action == "cancel":
        update["status"] = "cancelled"
    replacement_ref = str(value.get("candidate_chapter_version_id") or "")
    direction = str(value.get("direction") or "").strip()
    if replacement_ref:
        if action != "accept":
            raise ValueError("Only an accept decision may select an edited chapter candidate")
        replacement = executor.chapters.read(run_id, chapter_id, replacement_ref).artifact
        if replacement.chapter_id != chapter_id or replacement.author_status not in {"candidate", "edited"}:
            raise ValueError("Edited chapter candidate does not match the active chapter decision")
        refs = dict(state.get("chapter_version_refs") or {})
        refs[chapter_id] = replacement_ref
        update["chapter_version_refs"] = refs
    if action == "regenerate":
        if not direction:
            raise ValueError("A targeted chapter revision requires a direction")
        attempts = dict(state.get("chapter_attempts") or {})
        attempts[chapter_id] = int(attempts.get(chapter_id) or 1) + 1
        directions = dict(state.get("chapter_revision_directions") or {})
        directions[chapter_id] = direction
        update["chapter_attempts"] = attempts
        update["chapter_revision_directions"] = directions

    executor.events.append(
        run_id,
        event_id=f"{decision_id}:{action}:resolved",
        type="decision.resolved",
        stage_id="text",
        node_id="text.author_decision",
        chapter_id=chapter_id,
        status=action,
        payload={
            "decision_id": decision_id,
            "action": action,
            "artifact_ref": replacement_ref or candidate_ref,
            "quality_decision": _resolved_quality_decision(
                quality_decision,
                action,
            ).model_dump(mode="json"),
            **({"direction": direction} if direction else {}),
        },
    )
    return update


def save_edited_chapter_candidate(
    chapters: ChapterStore,
    events: EventProjection,
    *,
    run_id: str,
    chapter_id: str,
    source_version_id: str,
    payload: dict[str, Any],
) -> ChapterRecord:
    source = chapters.read(run_id, chapter_id, source_version_id)
    edited = validate_edited_chapter_candidate(
        source.artifact,
        chapter_id=chapter_id,
        source_version_id=source_version_id,
        payload=payload,
    )
    if edited.content == source.artifact.content:
        return source
    edit_digest = _chapter_edit_digest(
        {
            "chapter_id": chapter_id,
            "source_version_id": source_version_id,
            "content": edited.content,
        }
    )
    candidate = edited.model_copy(
        update={
            "version_id": f"{chapter_id}-edit-{edit_digest[:16]}",
            "author_status": "edited",
        }
    )
    record = chapters.write(run_id, candidate.model_dump(mode="json"))
    events.append(
        run_id,
        event_id=f"{run_id}:{chapter_id}:{record.version_id}:candidate",
        type="artifact.candidate_ready",
        stage_id="text",
        node_id="text.author_decision",
        chapter_id=chapter_id,
        status="edited",
        payload_ref=record.version_id,
    )
    return record


def validate_edited_chapter_candidate(
    source: ChapterArtifact,
    *,
    chapter_id: str,
    source_version_id: str,
    payload: dict[str, Any],
) -> ChapterArtifact:
    edited = ChapterArtifact.model_validate(payload)
    if edited.chapter_id != chapter_id or edited.version_id != source_version_id:
        raise ValueError("Edited chapter must target the active immutable candidate")
    if edited.author_status not in {"candidate", "edited"}:
        raise ValueError("Only a candidate chapter may be edited before acceptance")
    if edited.title != source.title:
        raise ValueError("Chapter title is owned by the frozen Detail Artifact")
    return edited


def _validate_resume(
    value: Any,
    decision_id: str,
    domain_revision: int,
    allowed_actions: list[ChapterDecisionAction],
) -> ChapterDecisionAction:
    if not isinstance(value, dict) or value.get("decision_id") != decision_id:
        raise ValueError("Chapter decision id does not match the active interrupt")
    if int(value.get("domain_revision", -1)) != domain_revision:
        raise ValueError("Chapter decision domain revision is stale")
    action = value.get("action")
    if action not in allowed_actions:
        raise ValueError("Unsupported chapter decision action")
    return action


def chapter_revision_direction(findings: list[dict[str, Any]]) -> str:
    return quality_revision_direction(findings)


def _resolved_quality_decision(
    decision: QualityDecision,
    action: ChapterDecisionAction,
) -> QualityDecision:
    regeneration_used = decision.regeneration_used + (1 if action == "regenerate" else 0)
    return decision.model_copy(
        update={
            "accepted": action == "accept",
            "regeneration_used": regeneration_used,
        }
    )


def _chapter_regeneration_count(
    executor: StageExecutor,
    run_id: str,
    chapter_id: str,
) -> int:
    return sum(
        1
        for event in executor.events.read(run_id)
        if event.type == "decision.resolved"
        and event.node_id == "text.author_decision"
        and str((event.payload or {}).get("decision_id") or "").startswith(
            f"{run_id}:{chapter_id}:"
        )
        and (event.payload or {}).get("action") == "regenerate"
    )


def _chapter_edit_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "ChapterDecisionAction",
    "MAX_CANDIDATE_REGENERATIONS",
    "chapter_revision_direction",
    "request_chapter_decision",
    "save_edited_chapter_candidate",
    "validate_edited_chapter_candidate",
]
