from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


class ChapterRevisionError(RuntimeError):
    pass


OPERATION_LABELS = {
    "rewrite": "重写",
    "expand": "扩写",
    "compress": "压缩",
    "restyle": "换风格",
}


def chapter_edit_signature(chapter: dict[str, Any]) -> str:
    payload = "\0".join(
        (
            str(chapter.get("id") or ""),
            str(_integer(chapter.get("version"), 0)),
            str(chapter.get("content") or ""),
            str(chapter.get("summary") or ""),
            "1" if chapter.get("summary_dirty") else "0",
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_selection(content: str, start: int, end: int, selected_text: str) -> None:
    if start < 0 or end <= start:
        raise ChapterRevisionError("请选择一段非空正文")
    if end - start > 6000:
        raise ChapterRevisionError("单次修订选区不能超过 6000 个字符")
    actual = utf16_slice(content, start, end)
    if actual != selected_text:
        raise ChapterRevisionError("选区已变化，请重新选择正文")


def utf16_slice(content: str, start: int, end: int) -> str:
    encoded = content.encode("utf-16-le")
    if end * 2 > len(encoded):
        raise ChapterRevisionError("选区超出当前正文范围")
    try:
        return encoded[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError as exc:
        raise ChapterRevisionError("选区边界切入了复合字符，请重新选择") from exc


def replace_utf16_selection(content: str, start: int, end: int, replacement: str) -> str:
    encoded = content.encode("utf-16-le")
    if end * 2 > len(encoded):
        raise ChapterRevisionError("选区超出当前正文范围")
    try:
        return (
            encoded[: start * 2]
            + replacement.encode("utf-16-le")
            + encoded[end * 2 :]
        ).decode("utf-16-le")
    except UnicodeDecodeError as exc:
        raise ChapterRevisionError("选区边界切入了复合字符，请重新选择") from exc


def candidate_signature(candidate: dict[str, Any]) -> str:
    payload = "\0".join(
        str(candidate.get(key) or "")
        for key in (
            "request_id",
            "chapter_id",
            "operation",
            "start",
            "end",
            "before",
            "replacement",
            "base_version",
            "base_signature",
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_revision_candidate(
    *,
    request_id: str,
    chapter: dict[str, Any],
    operation: str,
    direction: str,
    start: int,
    end: int,
    selected_text: str,
    replacement: str,
) -> dict[str, Any]:
    replacement = replacement.strip()
    if not replacement:
        raise ChapterRevisionError("模型没有返回可用的替换正文")
    if len(replacement) > 12000:
        raise ChapterRevisionError("替换正文超过 12000 个字符，请缩小选区")
    validate_selection(str(chapter.get("content") or ""), start, end, selected_text)
    candidate = {
        "request_id": request_id,
        "chapter_id": str(chapter.get("id") or ""),
        "operation": operation,
        "operation_label": OPERATION_LABELS[operation],
        "direction": direction,
        "start": start,
        "end": end,
        "before": selected_text,
        "replacement": replacement,
        "preview_content": replace_utf16_selection(
            str(chapter.get("content") or ""), start, end, replacement
        ),
        "base_version": _integer(chapter.get("version"), 0),
        "base_signature": chapter_edit_signature(chapter),
    }
    candidate["candidate_signature"] = candidate_signature(candidate)
    return candidate


def apply_revision_candidate(
    current_chapter: dict[str, Any],
    base_chapter: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if chapter_edit_signature(base_chapter) != candidate.get("base_signature"):
        raise ChapterRevisionError("候选稿基线已变化，请重新生成")
    validate_selection(
        str(base_chapter.get("content") or ""),
        _integer(candidate.get("start"), -1),
        _integer(candidate.get("end"), -1),
        str(candidate.get("before") or ""),
    )
    if candidate_signature(candidate) != candidate.get("candidate_signature"):
        raise ChapterRevisionError("候选稿签名无效，请重新生成")
    next_content = replace_utf16_selection(
        str(base_chapter.get("content") or ""),
        _integer(candidate.get("start"), -1),
        _integer(candidate.get("end"), -1),
        str(candidate.get("replacement") or ""),
    )
    history = _history_with_current(current_chapter, base_chapter)
    version = max(
        _integer(current_chapter.get("version"), 0),
        _integer(base_chapter.get("version"), 0),
    ) + 1
    revisions = _dict_list(base_chapter.get("revision_history"))
    revisions.append(
        {
            "id": f"selection-{candidate['request_id']}",
            "type": "selection_revision",
            "status": "draft",
            "label": f"{candidate.get('operation_label') or '局部修订'} · v{version}",
            "detail": f"替换 {len(str(candidate.get('before') or ''))} 字，章节摘要待同步。",
            "operation": candidate.get("operation"),
            "request_id": candidate.get("request_id"),
            "created_at": _now(),
        }
    )
    return {
        **base_chapter,
        "content": next_content,
        "words": len(next_content),
        "version": version,
        "commit_signature": "",
        "summary_dirty": True,
        "revision_history": revisions,
        "version_history": history,
    }


def restore_chapter_version(
    current_chapter: dict[str, Any],
    base_chapter: dict[str, Any],
    version_id: str,
    request_id: str,
) -> dict[str, Any]:
    snapshots = _dict_list(base_chapter.get("version_history"))
    target = next((item for item in snapshots if item.get("id") == version_id), None)
    if target is None:
        raise ChapterRevisionError("找不到要恢复的章节版本")
    content = str(target.get("content") or "")
    summary = str(target.get("summary") or "")
    if not content.strip() or not summary.strip():
        raise ChapterRevisionError("历史版本正文或摘要不完整，无法恢复")
    history = _history_with_current(current_chapter, base_chapter)
    version = max(
        _integer(current_chapter.get("version"), 0),
        _integer(base_chapter.get("version"), 0),
    ) + 1
    revisions = _dict_list(base_chapter.get("revision_history"))
    revisions.append(
        {
            "id": f"restore-{request_id}",
            "type": "version_restore",
            "status": "applied",
            "label": f"恢复历史版本 · v{version}",
            "detail": f"由 v{target.get('version')} 创建新版本，版本号不回退。",
            "source_version_id": version_id,
            "request_id": request_id,
            "created_at": _now(),
        }
    )
    return {
        **base_chapter,
        "content": content,
        "summary": summary,
        "words": len(content),
        "version": version,
        "commit_signature": "",
        "summary_dirty": bool(target.get("summary_dirty")),
        "revision_history": revisions,
        "version_history": history,
    }


def chapter_snapshot(chapter: dict[str, Any], *, source: str, operation: str = "") -> dict[str, Any]:
    version = _integer(chapter.get("version"), 0)
    return {
        "id": f"{chapter.get('id') or 'chapter'}-v{version}",
        "version": version,
        "content": str(chapter.get("content") or ""),
        "summary": str(chapter.get("summary") or ""),
        "words": _integer(chapter.get("words"), len(str(chapter.get("content") or ""))),
        "summary_dirty": bool(chapter.get("summary_dirty")),
        "source": source,
        "operation": operation,
        "created_at": _now(),
        "artifact_signature": chapter_edit_signature(chapter),
    }


def _history_with_current(current_chapter: dict[str, Any], base_chapter: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [
        *_dict_list(current_chapter.get("version_history")),
        *_dict_list(base_chapter.get("version_history")),
    ]
    if chapter_edit_signature(current_chapter) != chapter_edit_signature(base_chapter):
        entries.append(chapter_snapshot(current_chapter, source="model_generation"))
    entries.append(chapter_snapshot(base_chapter, source=_chapter_source(base_chapter)))
    unique: dict[str, dict[str, Any]] = {}
    for item in entries:
        unique[str(item.get("id") or item.get("artifact_signature") or len(unique))] = item
    return list(unique.values())[-30:]


def _chapter_source(chapter: dict[str, Any]) -> str:
    revisions = _dict_list(chapter.get("revision_history"))
    if revisions and revisions[-1].get("type") == "manual_edit":
        return "manual_edit"
    if revisions and revisions[-1].get("type") == "selection_revision":
        return "selection_revision"
    return "model_generation"


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
