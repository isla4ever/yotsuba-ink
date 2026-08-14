from __future__ import annotations

from typing import Any, TYPE_CHECKING

from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.workflows.narrative_scale import (
    chapter_length_contract,
    count_prose_characters,
)

if TYPE_CHECKING:
    from novel_workflow.runtime.graph.stage_executor import StageExecutor


_MAX_LENGTH_ATTEMPTS = 3


def evaluate_chapter_length(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    chapter_number = int(state["active_chapter_number"])
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    candidate = executor.chapters.read(run_id, chapter_id, version_id).artifact
    detail_chapter = executor.detail(state).chapters[chapter_number - 1]
    if detail_chapter.ref != chapter_id:
        raise ValueError("Length review does not match the frozen Detail chapter")

    definition = executor.runs.definition(run_id)
    contract = chapter_length_contract(
        detail_chapter.target_characters,
        definition.quality_mode,
        scene_count=len(detail_chapter.scenes),
    )
    if contract is None:
        return {"chapter_gate_action": "review"}

    actual = count_prose_characters(candidate.content)
    if contract.min_characters <= actual <= contract.max_characters:
        return {"chapter_gate_action": "review"}

    attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
    if attempt >= _MAX_LENGTH_ATTEMPTS:
        raise ValueError(
            f"Chapter length remained outside {contract.min_characters}-"
            f"{contract.max_characters} characters after {attempt} attempts: {actual}"
        )

    attempts = dict(state.get("chapter_attempts") or {})
    attempts[chapter_id] = attempt + 1
    directions = dict(state.get("chapter_revision_directions") or {})
    directions[chapter_id] = (
        f"完整重写本章，保留冻结章题《{detail_chapter.title}》、全部场景转折与交接。"
        f"上一稿去除空白后为 {actual} 字；本稿目标 {contract.target_characters} 字，"
        f"必须落在 {contract.min_characters}-{contract.max_characters} 字。"
        "不要新增施工图之外的事件；不足时深化场景动作、感官和对话反应，"
        "超出时删除重复心理解释、总结和无效过场。"
    )
    return {
        "chapter_attempts": attempts,
        "chapter_revision_directions": directions,
        "chapter_gate_action": "regenerate",
    }


__all__ = ["evaluate_chapter_length"]
