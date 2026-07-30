from __future__ import annotations

import json
from typing import Any


def build_candidate_prompt(base_prompt: str, *, direction: str, candidate_index: int, previous: Any) -> str:
    return (
        f"{base_prompt}\n\n"
        "## 用户主动换稿要求\n"
        f"- 换稿方向: {direction}\n"
        f"- 当前候选序号: {candidate_index}\n"
        "- 必须生成一个完整、可替换当前阶段产物的结构化 JSON object。\n"
        "- 不要输出评审解释，不要返回 markdown，不要只修改局部片段。\n"
        "## 当前稿参考\n"
        f"{json.dumps(previous, ensure_ascii=False)[:6000] if previous is not None else '暂无当前稿'}"
    )


def chapter_candidate_artifact(result: Any, previous: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "chapters" in result:
        return result
    chapter_title = str(result.get("chapter_title") if isinstance(result, dict) else "第1章") or "第1章"
    content = str(result.get("content") if isinstance(result, dict) else result or "")
    previous_artifact = previous if isinstance(previous, dict) else {}
    chapters = previous_artifact.get("chapters") if isinstance(previous_artifact.get("chapters"), list) else []
    if chapters:
        first = dict(chapters[0])
        first.update({"title": chapter_title, "content": content, "words": len(content), "status": "completed"})
        next_chapters = [first, *chapters[1:]]
    else:
        next_chapters = [{"id": "chapter-1", "title": chapter_title, "content": content, "words": len(content), "status": "completed"}]
    return {
        "context_packet": previous_artifact.get("context_packet", {}),
        "chapter_deltas": [],
        "chapters": next_chapters,
        "quality_reports": previous_artifact.get("quality_reports", []),
        "wiki_writebacks": previous_artifact.get("wiki_writebacks", []),
        "chapter_summaries": previous_artifact.get("chapter_summaries", []),
    }


def artifact_preview(artifact: Any) -> str:
    if isinstance(artifact, dict):
        if artifact.get("selected_title") or artifact.get("synopsis"):
            return "\n".join(
                part
                for part in (
                    str(artifact.get("selected_title") or "").strip(),
                    str(artifact.get("synopsis") or "").strip(),
                )
                if part
            )
        for key in ("full_synopsis", "brief", "composition", "prompt"):
            if artifact.get(key):
                return str(artifact[key])
        if isinstance(artifact.get("volumes"), list):
            return "\n".join(str(item.get("volume_goal") or item.get("title") or "") for item in artifact["volumes"] if isinstance(item, dict))
        if isinstance(artifact.get("chapters"), list):
            return "\n".join(str(item.get("content") or item.get("goal") or item.get("title") or "") for item in artifact["chapters"][:2] if isinstance(item, dict))
    return "候选产物已生成，当前结构暂不支持内容预览。"


def preview_deltas(preview: str) -> list[str]:
    paragraphs = [part.strip() for part in preview.split("\n") if part.strip()]
    if paragraphs:
        return [f"{part}\n" for part in paragraphs[:6]]
    size = max(80, len(preview) // 3)
    return [preview[index : index + size] for index in range(0, len(preview), size) if preview[index : index + size]]


def candidate_history(draft_state: Any) -> list[dict[str, Any]]:
    if not isinstance(draft_state, dict):
        return []
    previous = draft_state.get("candidates") if isinstance(draft_state.get("candidates"), list) else []
    existing = draft_state.get("history") if isinstance(draft_state.get("history"), list) else []
    history: list[dict[str, Any]] = []
    for item in [*previous, *existing]:
        if not isinstance(item, dict) or not item.get("artifact"):
            continue
        key = str(item.get("candidate_id") or item.get("section") or "")
        if not key or any(str(candidate.get("candidate_id") or candidate.get("section") or "") == key for candidate in history):
            continue
        history.append(item)
    return history[:12]
