from __future__ import annotations

from typing import Any, Literal

from langgraph.types import interrupt

from novel_workflow.quality.manuscript_contracts import (
    ManuscriptQualityReport,
    build_manuscript_quality_report,
)
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState


ManuscriptDecisionAction = Literal["accept", "cancel"]


def evaluate_manuscript_gate(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    run_id = state["run_id"]
    detail = executor.detail(state)
    refs = state.get("chapter_version_refs") or {}
    chapters = [
        executor.chapters.read(run_id, chapter.ref, refs[chapter.ref]).artifact
        for chapter in detail.chapters
    ]
    story_state = executor.outbox.canon.resolved_state(
        run_id,
        as_of_chapter=len(detail.chapters),
        subject_ids=None,
    ).model_dump(mode="json")
    report = build_manuscript_quality_report(
        detail=detail,
        chapters=chapters,
        story_state=story_state,
        review_findings=_accepted_review_findings(executor, run_id),
    )
    decision_id = f"{run_id}:text:manuscript-quality"
    allowed_actions: list[ManuscriptDecisionAction] = (
        ["cancel"] if report.blockers else ["accept", "cancel"]
    )
    payload = {
        "type": "manuscript_quality_decision",
        "decision_id": decision_id,
        "thread_id": run_id,
        "node_id": "text.manuscript_quality_decision",
        "artifact_ref": report.report_id,
        "domain_revision": int(state.get("domain_revision") or 0),
        "allowed_actions": allowed_actions,
        "quality_report": report.model_dump(mode="json"),
    }
    executor.events.append(
        run_id,
        event_id=f"{decision_id}:evaluated",
        type="quality.manuscript_evaluated",
        stage_id="text",
        node_id="text.evaluate_manuscript",
        status="blocked" if report.blockers else "completed",
        payload=payload["quality_report"],
        payload_ref=report.report_id,
    )
    if state.get("quality_mode") == "fast" and not report.blockers:
        action: ManuscriptDecisionAction = "accept"
        resolution = "fast_clean_contract"
    else:
        executor.events.append(
            run_id,
            event_id=f"{decision_id}:required",
            type="decision.required",
            stage_id="text",
            node_id="text.manuscript_quality_decision",
            status="awaiting_decision",
            payload=payload,
        )
        value = interrupt(payload)
        action = _validate_resume(
            value,
            decision_id=decision_id,
            domain_revision=int(state.get("domain_revision") or 0),
            allowed_actions=allowed_actions,
        )
        resolution = "author"
    executor.events.append(
        run_id,
        event_id=f"{decision_id}:{action}:resolved",
        type="decision.resolved",
        stage_id="text",
        node_id="text.manuscript_quality_decision",
        status=action,
        payload={
            "decision_id": decision_id,
            "action": action,
            "artifact_ref": report.report_id,
            "resolution": resolution,
            "quality_report": report.model_dump(mode="json"),
        },
        payload_ref=report.report_id,
    )
    return {
        "manuscript_gate_action": action,
        "status": "cancelled" if action == "cancel" else "running",
    }


def _accepted_review_findings(
    executor: StageExecutor,
    run_id: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for event in executor.events.read(run_id):
        if event.type != "decision.resolved" or event.node_id != "text.author_decision":
            continue
        payload = event.payload or {}
        if payload.get("action") != "accept":
            continue
        decision = payload.get("quality_decision")
        if not isinstance(decision, dict):
            continue
        for finding in decision.get("review_warnings") or []:
            if isinstance(finding, dict):
                findings.append({**finding, "chapter_id": event.chapter_id})
    return findings


def _validate_resume(
    value: Any,
    *,
    decision_id: str,
    domain_revision: int,
    allowed_actions: list[ManuscriptDecisionAction],
) -> ManuscriptDecisionAction:
    if not isinstance(value, dict) or value.get("decision_id") != decision_id:
        raise ValueError("Manuscript quality decision id does not match the active interrupt")
    if int(value.get("domain_revision", -1)) != domain_revision:
        raise ValueError("Manuscript quality decision domain revision is stale")
    action = value.get("action")
    if action not in allowed_actions:
        raise ValueError("Unsupported manuscript quality decision action")
    return action


__all__ = [
    "ManuscriptDecisionAction",
    "evaluate_manuscript_gate",
]
