from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from langgraph.types import interrupt

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact
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
    reason: dict[str, Any],
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    candidate_ref = (state.get("chapter_version_refs") or {})[chapter_id]
    decision_id = f"{run_id}:{chapter_id}:{candidate_ref}:author-decision"
    reason = dict(reason)
    blocking_findings = _finding_records(reason.get("blocking_findings"))
    warning_findings = _finding_records(reason.get("warning_findings"))
    recommended_direction = chapter_revision_direction(
        blocking_findings or warning_findings
    )
    if recommended_direction:
        reason["recommended_revision_direction"] = recommended_direction
    regeneration_count = _chapter_regeneration_count(executor, run_id, chapter_id)
    allowed_actions: list[ChapterDecisionAction] = []
    if not blocking_findings:
        allowed_actions.append("accept")
    if regeneration_count < MAX_CANDIDATE_REGENERATIONS:
        allowed_actions.append("regenerate")
    allowed_actions.append("cancel")
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
        "reason": reason,
    }
    if state.get("quality_mode") == "fast":
        if blocking_findings:
            if "regenerate" not in allowed_actions:
                raise ValueError(
                    "Chapter still violates a hard quality gate after its single automatic regeneration"
                )
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
    """Turn reviewer evidence into one bounded prose revision instruction."""

    items: list[str] = []
    for index, finding in enumerate(findings[:3], start=1):
        claim = str(finding.get("claim") or finding.get("code") or "审校问题").strip()
        evidence = str(finding.get("evidence") or "").strip()
        excerpt = evidence[:80]
        items.append(f"{index}. {claim}" + (f"；证据：{excerpt}" if excerpt else ""))
    if not items:
        return ""
    return (
        "只修复以下审校问题，不改变冻结章名、细纲场景顺序、主体职责或未点名情节："
        + " ".join(items)
        + "。修改后核对本章结尾与下一章 handoff。"
    )


def _finding_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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
        and event.chapter_id == chapter_id
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
