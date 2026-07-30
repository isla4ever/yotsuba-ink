from __future__ import annotations

import hashlib
import json
from typing import Any

from novel_workflow.workflows.schemas import ChapterContextPacket, ChapterDraft, ChapterProgressItem, SelectedVariant


def empty_chapter_artifact(target: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "running",
        "target_chapters": target,
        "context_packet": {},
        "context_packets": [],
        "chapter_deltas": [],
        "chapters": [],
        "quality_reports": [],
        "wiki_writebacks": [],
        "chapter_summaries": [],
    }


def normalize_chapter_artifact(value: Any, target: int) -> dict[str, Any]:
    artifact = empty_chapter_artifact(target)
    if not isinstance(value, dict):
        return artifact
    chapters = value.get("chapters")
    if isinstance(chapters, list):
        artifact["chapters"] = [dict(item) for item in chapters if isinstance(item, dict)]
    artifact["status"] = "completed" if value.get("status") == "completed" else "running"
    artifact["schema_version"] = max(1, _integer(value.get("schema_version"), 1))
    artifact["target_chapters"] = max(target, _integer(value.get("target_chapters"), target))
    artifact["chapter_deltas"] = _dict_list(value.get("chapter_deltas"))
    return rebuild_chapter_artifact(artifact)


def initialize_chapter_progress(state: Any, node_id: str, target: int, artifact: dict[str, Any]) -> None:
    existing = {item.chapter: item for item in state.chapter_progress if item.node_id == node_id}
    committed = {chapter_index(item) for item in artifact["chapters"] if item.get("status") == "completed"}
    next_progress: list[ChapterProgressItem] = []
    for index in range(1, target + 1):
        chapter = f"第{index}章"
        item = existing.get(chapter) or ChapterProgressItem(volume="第一卷", chapter=chapter, node_id=node_id)
        item.node_id = node_id
        if index in committed:
            saved = chapter_at(artifact, index)
            item.status = "completed"
            item.words = _integer(saved.get("words") if saved else 0, 0)
            quality = saved.get("quality_report") if isinstance(saved, dict) else {}
            item.quality_score = float(quality.get("score") or item.quality_score or 0) if isinstance(quality, dict) else item.quality_score
        elif item.status == "completed":
            item.status = "planned"
            item.words = 0
            item.quality_score = 0
        next_progress.append(item)
    state.chapter_progress = [item for item in state.chapter_progress if item.node_id != node_id] + next_progress


def chapter_at(artifact: dict[str, Any], index: int) -> dict[str, Any] | None:
    return next((item for item in artifact["chapters"] if chapter_index(item) == index), None)


def chapter_index(chapter: dict[str, Any]) -> int:
    chapter_id = str(chapter.get("id") or "")
    if chapter_id.startswith("chapter-") and chapter_id[8:].isdigit():
        return int(chapter_id[8:])
    title = str(chapter.get("title") or "")
    digits = "".join(character for character in title if character.isdigit())
    return int(digits) if digits else 0


def upsert_context_packet(state: Any, packet: ChapterContextPacket) -> None:
    state.chapter_context_packets = [item for item in state.chapter_context_packets if item.chapter != packet.chapter]
    state.chapter_context_packets.append(packet)
    state.chapter_context_packets.sort(key=lambda item: item.chapter_index)


def upsert_chapter_draft(state: Any, draft: ChapterDraft) -> None:
    state.chapter_drafts = [
        item for item in state.chapter_drafts
        if not (item.chapter == draft.chapter and item.variant_id == draft.variant_id)
    ]
    state.chapter_drafts.append(draft)


def upsert_selected_variant(state: Any, selected: SelectedVariant) -> None:
    state.selected_variants = [
        item for item in state.selected_variants
        if not (item.node_id == selected.node_id and item.chapter == selected.chapter)
    ]
    state.selected_variants.append(selected)


def drafting_chapter(
    result: dict[str, Any],
    *,
    index: int,
    content: str,
    context_packet: ChapterContextPacket,
) -> dict[str, Any]:
    generated_title = str(result.get("chapter_title") or f"第{index}章").strip()
    return {
        "id": f"chapter-{index}",
        "title": f"第{index}章",
        "generated_title": generated_title,
        "content": content,
        "words": len(content),
        "status": "drafting",
        "version": 0,
        "commit_signature": "",
        "summary": str(result.get("summary") or "").strip(),
        "context_packet": context_packet.model_dump(),
        "wiki_writebacks": _dict_list(result.get("wiki_writebacks")),
        "character_shift": result.get("character_shift") or "",
        "foreshadow_updates": _dict_list(result.get("foreshadow_updates")),
        "quality_report": {},
        "revision_history": [],
        "version_history": [],
    }


def prepare_chapter_commit(
    chapter: dict[str, Any],
    *,
    content: str,
    quality_report: dict[str, Any],
    revision_history: list[dict[str, Any]],
) -> dict[str, Any]:
    prepared = {
        **chapter,
        "content": content,
        "words": len(content),
        "status": "committing",
        "quality_report": quality_report,
        "revision_history": revision_history,
    }
    prepared["commit_signature"] = chapter_commit_signature(prepared)
    return prepared


def complete_chapter_commit(chapter: dict[str, Any]) -> dict[str, Any]:
    return {**chapter, "status": "completed", "version": max(1, _integer(chapter.get("version"), 0) + 1)}


def upsert_chapter(artifact: dict[str, Any], chapter: dict[str, Any]) -> dict[str, Any]:
    index = chapter_index(chapter)
    artifact["chapters"] = [item for item in artifact["chapters"] if chapter_index(item) != index]
    artifact["chapters"].append(chapter)
    artifact["chapters"].sort(key=chapter_index)
    return rebuild_chapter_artifact(artifact)


def rebuild_chapter_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    chapters = artifact["chapters"]
    packets = [item.get("context_packet") for item in chapters if isinstance(item.get("context_packet"), dict)]
    reports = [item.get("quality_report") for item in chapters if isinstance(item.get("quality_report"), dict) and item.get("quality_report")]
    artifact["context_packets"] = packets
    artifact["context_packet"] = packets[-1] if packets else {}
    artifact["quality_reports"] = reports
    artifact["wiki_writebacks"] = [writeback for item in chapters for writeback in _dict_list(item.get("wiki_writebacks"))]
    artifact["chapter_summaries"] = [
        {"chapter": item.get("title") or item.get("id"), "summary": item.get("summary")}
        for item in chapters
        if str(item.get("summary") or "").strip()
    ]
    target = _integer(artifact.get("target_chapters"), len(chapters) or 1)
    artifact["status"] = "completed" if len(chapters) >= target and all(item.get("status") == "completed" for item in chapters[:target]) else "running"
    return artifact


def chapter_commit_signature(chapter: dict[str, Any]) -> str:
    payload = {
        key: chapter.get(key)
        for key in (
            "id",
            "title",
            "generated_title",
            "content",
            "summary",
            "context_packet",
            "wiki_writebacks",
            "character_shift",
            "foreshadow_updates",
            "quality_report",
            "revision_history",
        )
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value] if isinstance(value, list) else []


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
