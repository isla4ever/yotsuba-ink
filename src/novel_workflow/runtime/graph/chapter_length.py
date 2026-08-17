from __future__ import annotations

from typing import Any, TYPE_CHECKING

from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.workflows.narrative_scale import (
    chapter_length_contract,
    count_prose_characters,
)

if TYPE_CHECKING:
    from novel_workflow.runtime.graph.stage_executor import StageExecutor


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
    executor.events.append(
        run_id,
        event_id=f"{run_id}:{chapter_id}:{version_id}:length-warning",
        type="quality.warning",
        stage_id="text",
        node_id="text.check_length_contract",
        chapter_id=chapter_id,
        status="warning",
        payload={
            "code": "chapter_length_soft_band",
            "actual_characters": actual,
            "target_characters": contract.target_characters,
            "soft_bounds": [contract.min_characters, contract.max_characters],
        },
        payload_ref=version_id,
    )
    return {"chapter_gate_action": "review"}


__all__ = ["evaluate_chapter_length"]
