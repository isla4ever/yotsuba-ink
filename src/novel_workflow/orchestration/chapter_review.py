from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from novel_workflow.orchestration.chapter_artifact import upsert_chapter
from novel_workflow.orchestration.chapter_review_model import (
    ChapterReviewError,
    build_writeback_proposal,
    decide_writeback_proposal,
    synchronize_chapter_summary,
)
from novel_workflow.orchestration.chapter_revision_model import chapter_edit_signature
from novel_workflow.orchestration.chapter_revision_support import (
    commit_artifact_events,
    revision_context,
    trim_revision_state,
    update_chapter_draft,
    validated_base_chapter,
)
from novel_workflow.quality.chapter_repair_targets import build_chapter_repair_targets
from novel_workflow.workflows.schemas import ChapterContextPacket, WorkflowDefinition


def sync_chapter_summary_and_review(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    payload: Any,
) -> dict[str, Any]:
    stored, state, node, artifact, current = revision_context(
        runner, workflow, run_id, payload.node_id, payload.chapter_id
    )
    request_signature = _request_signature(payload)
    existing = state.chapter_review_state.get(payload.request_id, {})
    if existing:
        if existing.get("request_signature") != request_signature:
            raise ChapterReviewError("request_id 已被其他章节复检请求使用")
        if existing.get("status") == "completed":
            return copy.deepcopy(existing["result"])

    base = validated_base_chapter(current, payload)
    if str(base.get("summary") or "").strip() != payload.summary.strip():
        raise ChapterReviewError("摘要内容与当前编辑稿不一致")
    synced = synchronize_chapter_summary(base, payload.summary, payload.request_id)
    packet = ChapterContextPacket.model_validate(synced.get("context_packet") or {})
    report = runner.quality_engine.check_stage(
        node,
        str(synced.get("content") or ""),
        story_bible=state.story_bible,
        mode=workflow.quality_mode,
        chapter=str(synced.get("title") or ""),
        context_packet=packet,
    )
    artifact_signature = chapter_edit_signature(synced)
    report_dump = {
        **report.model_dump(),
        "artifact_signature": artifact_signature,
        "chapter_version": int(synced.get("version") or 0),
        "record_type": "chapter_quality_recheck",
        "request_id": payload.request_id,
    }
    repair_targets = build_chapter_repair_targets(
        str(synced.get("content") or ""),
        report.findings,
        chapter_id=str(synced.get("id") or ""),
        chapter=str(synced.get("title") or ""),
        artifact_signature=artifact_signature,
        chapter_version=int(synced.get("version") or 0),
    )
    for finding_dump, target in zip(report_dump.get("findings", []), repair_targets, strict=True):
        finding_dump["id"] = target["finding_id"]
    report_dump["repair_targets"] = repair_targets
    synced["quality_report"] = report_dump
    synced["quality_recheck"] = {
        "status": "passed" if report.passed else "blocked",
        "artifact_signature": artifact_signature,
        "chapter_version": int(synced.get("version") or 0),
        "request_id": payload.request_id,
        "report": report_dump,
        "repair_targets": repair_targets,
    }
    proposal = build_writeback_proposal(synced, report_dump, canon_facts=state.canon_facts)
    synced["writeback_proposal"] = proposal
    artifact = upsert_chapter(copy.deepcopy(artifact), synced)
    update_chapter_draft(state, synced)
    state.quality_reports = [
        item for item in state.quality_reports
        if not (
            item.get("record_type") == "chapter_quality_recheck"
            and item.get("chapter") == synced.get("title")
        )
    ]
    state.quality_reports.append(report_dump)
    events = _review_events(run_id, node, synced, report_dump, proposal, artifact, payload.request_id)
    result = {
        "artifact": artifact,
        "chapter": synced,
        "quality_report": report_dump,
        "proposal": proposal,
        "events": events,
    }
    state.chapter_review_state[payload.request_id] = {
        "status": "completed",
        "request_signature": request_signature,
        "result": result,
    }
    _trim_review_state(state)
    return commit_artifact_events(
        runner,
        stored,
        state,
        node.id,
        node.output_key or node.id,
        artifact,
        str(synced.get("id") or ""),
        events,
    ) | {"quality_report": report_dump, "proposal": proposal}


def decide_chapter_writeback(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    payload: Any,
) -> dict[str, Any]:
    stored, state, node, artifact, current = revision_context(
        runner, workflow, run_id, payload.node_id, payload.chapter_id
    )
    request_signature = _request_signature(payload)
    existing = state.chapter_review_state.get(payload.request_id, {})
    if existing:
        if existing.get("request_signature") != request_signature:
            raise ChapterReviewError("request_id 已被其他提案决策使用")
        if existing.get("status") == "completed":
            return copy.deepcopy(existing["result"])
    if int(current.get("version") or 0) != payload.base_version:
        raise ChapterReviewError("章节版本已变化，请刷新后重试")
    if chapter_edit_signature(current) != payload.base_signature:
        raise ChapterReviewError("章节复检签名已过期，请刷新后重试")
    decided = decide_writeback_proposal(
        current,
        proposal_id=payload.proposal_id,
        proposal_signature=payload.proposal_signature,
        decision=payload.decision,
        request_id=payload.request_id,
        conflict_resolutions=payload.conflict_resolutions,
    )
    artifact = upsert_chapter(copy.deepcopy(artifact), decided)
    update_chapter_draft(state, decided)
    event_type = f"chapter_writeback_proposal_{payload.decision}"
    event = {
        "type": event_type,
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": decided.get("title"),
        "chapter_id": decided.get("id"),
        "request_id": payload.request_id,
        "proposal": decided.get("writeback_proposal"),
        "artifact": artifact,
        "message": "写回提案已接受，将在正文定稿时正式写入。"
        if payload.decision == "accepted"
        else "写回提案已拒绝，正文与摘要仍可继续定稿。",
    }
    result = {"artifact": artifact, "chapter": decided, "events": [event]}
    state.chapter_review_state[payload.request_id] = {
        "status": "completed",
        "request_signature": request_signature,
        "result": result,
    }
    _trim_review_state(state)
    return commit_artifact_events(
        runner,
        stored,
        state,
        node.id,
        node.output_key or node.id,
        artifact,
        str(decided.get("id") or ""),
        [event],
    )


def _review_events(
    run_id: str,
    node: Any,
    chapter: dict[str, Any],
    report: dict[str, Any],
    proposal: dict[str, Any],
    artifact: dict[str, Any],
    request_id: str,
) -> list[dict[str, Any]]:
    common = {
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": chapter.get("title"),
        "chapter_id": chapter.get("id"),
        "request_id": request_id,
    }
    return [
        {"type": "chapter_summary_synced", **common, "artifact": artifact, "message": "章节摘要已绑定当前正文版本。"},
        {"type": "quality_recheck_completed", **common, "quality_report": report, "message": "章节质量复检已完成。"},
        {"type": "chapter_writeback_proposal_generated", **common, "proposal": proposal, "artifact": artifact, "message": "章节写回提案已生成。"},
    ]


def _request_signature(payload: Any) -> str:
    data = payload.model_dump(exclude={"request_id"})
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _trim_review_state(state: Any) -> None:
    trim_revision_state(state)
    if len(state.chapter_review_state) > 40:
        state.chapter_review_state = dict(list(state.chapter_review_state.items())[-40:])
