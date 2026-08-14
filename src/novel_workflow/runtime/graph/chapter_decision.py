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
    payload = {
        "type": "chapter_author_decision",
        "decision_id": decision_id,
        "thread_id": run_id,
        "node_id": "text.author_decision",
        "chapter_id": chapter_id,
        "artifact_ref": candidate_ref,
        "domain_revision": state.get("domain_revision", 0),
        "allowed_actions": ["accept", "regenerate", "cancel"],
        "reason": reason,
    }
    if state.get("quality_mode") == "fast":
        action: ChapterDecisionAction = "accept"
        value: dict[str, Any] = {}
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
        action = _validate_resume(value, decision_id, int(state.get("domain_revision") or 0))

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
    edited = ChapterArtifact.model_validate(payload)
    if edited.chapter_id != chapter_id or edited.version_id != source_version_id:
        raise ValueError("Edited chapter must target the active immutable candidate")
    if edited.author_status not in {"candidate", "edited"}:
        raise ValueError("Only a candidate chapter may be edited before acceptance")
    if edited.title != source.artifact.title:
        raise ValueError("Chapter title is owned by the frozen Detail Artifact")
    if edited.content == source.artifact.content:
        return source
    signature = _signature(
        {
            "chapter_id": chapter_id,
            "source_version_id": source_version_id,
            "content": edited.content,
        }
    )
    candidate = edited.model_copy(
        update={
            "version_id": f"{chapter_id}-edit-{signature[:16]}",
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


def _validate_resume(value: Any, decision_id: str, domain_revision: int) -> ChapterDecisionAction:
    if not isinstance(value, dict) or value.get("decision_id") != decision_id:
        raise ValueError("Chapter decision id does not match the active interrupt")
    if int(value.get("domain_revision", -1)) != domain_revision:
        raise ValueError("Chapter decision domain revision is stale")
    action = value.get("action")
    if action not in {"accept", "regenerate", "cancel"}:
        raise ValueError("Unsupported chapter decision action")
    return action


def _signature(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "ChapterDecisionAction",
    "request_chapter_decision",
    "save_edited_chapter_candidate",
]
