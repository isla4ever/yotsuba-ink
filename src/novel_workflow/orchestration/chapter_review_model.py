from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from novel_workflow.orchestration.chapter_revision_model import (
    ChapterRevisionError,
    chapter_edit_signature,
)
from novel_workflow.memory.canon import effective_writebacks_for_proposal, preview_canon_writebacks


class ChapterReviewError(ChapterRevisionError):
    pass


FINAL_PROPOSAL_STATUSES = {"accepted", "rejected", "not_required"}


def synchronize_chapter_summary(
    chapter: dict[str, Any],
    summary: str,
    request_id: str,
) -> dict[str, Any]:
    summary = summary.strip()
    if not summary:
        raise ChapterReviewError("章节摘要不能为空")
    revisions = _dict_list(chapter.get("revision_history"))
    revisions = [
        {**item, "status": "synced"}
        if item.get("status") == "draft" and item.get("type") in {"manual_edit", "selection_revision"}
        else item
        for item in revisions
    ]
    revisions.append(
        {
            "id": f"summary-sync-{request_id}",
            "type": "summary_sync",
            "status": "completed",
            "label": f"摘要同步 · v{int(chapter.get('version') or 0)}",
            "detail": "章节摘要已与当前正文版本绑定并完成质量复检。",
            "request_id": request_id,
            "created_at": _now(),
        }
    )
    return {
        **chapter,
        "summary": summary,
        "summary_dirty": False,
        "commit_signature": "",
        "revision_history": revisions,
    }


def build_writeback_proposal(
    chapter: dict[str, Any],
    quality_report: dict[str, Any],
    *,
    canon_facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    artifact_signature = chapter_edit_signature(chapter)
    wiki = _dict_list(chapter.get("wiki_writebacks"))
    foreshadows = _dict_list(chapter.get("foreshadow_updates"))
    character = copy.deepcopy(chapter.get("character_shift") or "")
    has_character = bool(character.strip()) if isinstance(character, str) else bool(character)
    has_changes = bool(wiki or foreshadows or has_character)
    canon = preview_canon_writebacks(
        canon_facts or [],
        wiki,
        chapter_id=str(chapter.get("id") or ""),
        chapter=str(chapter.get("title") or ""),
        chapter_version=int(chapter.get("version") or 0),
        artifact_signature=artifact_signature,
    )
    passed = bool(quality_report.get("passed"))
    status = "blocked" if not passed else "pending" if has_changes else "not_required"
    proposal = {
        "id": f"proposal-{chapter.get('id')}-v{chapter.get('version')}-{artifact_signature[:12]}",
        "chapter_id": str(chapter.get("id") or ""),
        "chapter": str(chapter.get("title") or ""),
        "version": int(chapter.get("version") or 0),
        "artifact_signature": artifact_signature,
        "status": status,
        "wiki_writebacks": wiki,
        "character_shift": character,
        "foreshadow_updates": foreshadows,
        "counts": {
            "wiki": len(wiki),
            "character": 1 if has_character else 0,
            "foreshadow": len(foreshadows),
        },
        "created_at": _now(),
        "canon": canon,
    }
    proposal["proposal_signature"] = writeback_proposal_signature(proposal)
    return proposal


def decide_writeback_proposal(
    chapter: dict[str, Any],
    *,
    proposal_id: str,
    proposal_signature: str,
    decision: str,
    request_id: str,
    conflict_resolutions: dict[str, str] | None = None,
) -> dict[str, Any]:
    proposal = copy.deepcopy(chapter.get("writeback_proposal"))
    if not isinstance(proposal, dict) or proposal.get("id") != proposal_id:
        raise ChapterReviewError("找不到当前章节的写回提案")
    if proposal.get("proposal_signature") != proposal_signature:
        raise ChapterReviewError("写回提案签名不匹配，请刷新后重试")
    if writeback_proposal_signature(proposal) != proposal_signature:
        raise ChapterReviewError("写回提案内容已变化，请重新复检")
    if proposal.get("artifact_signature") != chapter_edit_signature(chapter):
        raise ChapterReviewError("正文版本已变化，旧写回提案不能继续使用")
    if proposal.get("status") not in {"pending", decision}:
        raise ChapterReviewError("当前写回提案不可再决策")
    canon = proposal.get("canon") if isinstance(proposal.get("canon"), dict) else {}
    conflicts = [item for item in canon.get("conflicts", []) if isinstance(item, dict)]
    resolutions = conflict_resolutions or {}
    if decision == "accepted":
        missing = [str(item.get("id") or "") for item in conflicts if resolutions.get(str(item.get("id") or "")) not in {"keep_existing", "replace_existing"}]
        if missing:
            raise ChapterReviewError("Canon 存在未决冲突，请先选择保留既有事实或采用新事实")
        if set(resolutions) - {str(item.get("id") or "") for item in conflicts}:
            raise ChapterReviewError("Canon 冲突决策包含未知条目")
    proposal.update(
        {
            "status": decision,
            "decision_request_id": request_id,
            "decided_at": _now(),
            "conflict_resolutions": resolutions,
        }
    )
    revisions = _dict_list(chapter.get("revision_history"))
    revisions.append(
        {
            "id": f"proposal-decision-{request_id}",
            "type": "writeback_proposal_decision",
            "status": decision,
            "label": "接受写回提案" if decision == "accepted" else "拒绝写回提案",
            "detail": "正式定稿时按本次决策处理 Wiki、人物与伏笔变化。",
            "request_id": request_id,
            "created_at": _now(),
        }
    )
    return {**chapter, "writeback_proposal": proposal, "revision_history": revisions}


def chapter_review_errors(artifact: Any) -> list[str]:
    if not isinstance(artifact, dict) or not isinstance(artifact.get("chapters"), list):
        return []
    errors: list[str] = []
    for chapter in artifact["chapters"]:
        if not isinstance(chapter, dict):
            continue
        recheck = chapter.get("quality_recheck")
        proposal = chapter.get("writeback_proposal")
        if not isinstance(recheck, dict) and not isinstance(proposal, dict):
            continue
        label = str(chapter.get("title") or chapter.get("id") or "章节")
        signature = chapter_edit_signature(chapter)
        if not isinstance(recheck, dict) or recheck.get("status") != "passed":
            errors.append(f"{label}质量复检尚未通过")
        elif recheck.get("artifact_signature") != signature:
            errors.append(f"{label}质量复检已过期")
        if not isinstance(proposal, dict) or proposal.get("status") not in FINAL_PROPOSAL_STATUSES:
            errors.append(f"{label}写回提案尚未完成决策")
        elif proposal.get("artifact_signature") != signature:
            errors.append(f"{label}写回提案已过期")
        elif proposal.get("proposal_signature") != writeback_proposal_signature(proposal):
            errors.append(f"{label}写回提案签名无效")
    return errors


def chapter_with_decided_writebacks(chapter: dict[str, Any]) -> dict[str, Any]:
    proposal = chapter.get("writeback_proposal")
    if not isinstance(proposal, dict):
        return chapter
    status = proposal.get("status")
    if status == "accepted":
        return {
            **chapter,
            "wiki_writebacks": effective_writebacks_for_proposal(proposal),
            "character_shift": copy.deepcopy(proposal.get("character_shift") or ""),
            "foreshadow_updates": _dict_list(proposal.get("foreshadow_updates")),
        }
    if status in {"rejected", "not_required"}:
        return {**chapter, "wiki_writebacks": [], "character_shift": "", "foreshadow_updates": []}
    raise ChapterReviewError("写回提案尚未完成决策，不能正式定稿")


def writeback_proposal_signature(proposal: dict[str, Any]) -> str:
    payload = {
        key: proposal.get(key)
        for key in (
            "id",
            "chapter_id",
            "chapter",
            "version",
            "artifact_signature",
            "wiki_writebacks",
            "character_shift",
            "foreshadow_updates",
            "counts",
            "canon",
        )
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
