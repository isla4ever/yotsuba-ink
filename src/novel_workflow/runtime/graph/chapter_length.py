from __future__ import annotations

from typing import Any, TYPE_CHECKING

from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.workflows.narrative_scale import (
    ChapterLengthContract,
    chapter_length_contract,
    count_prose_characters,
    minimum_viable_book_characters,
    minimum_viable_chapter_characters,
    soft_book_length_bounds,
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
    base_contract = chapter_length_contract(
        detail_chapter.target_characters,
        definition.quality_mode,
        scene_count=len(detail_chapter.scenes),
    )
    if base_contract is None:
        return {"chapter_gate_action": "review"}
    actual = count_prose_characters(candidate.content)
    if not base_contract.min_characters <= actual <= base_contract.max_characters:
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
                "target_characters": base_contract.target_characters,
                "soft_bounds": [base_contract.min_characters, base_contract.max_characters],
            },
            payload_ref=version_id,
        )
    viable_minimum = minimum_viable_chapter_characters(base_contract)
    if actual < viable_minimum:
        return _severe_underlength_blocker(
            executor,
            state,
            version_id=version_id,
            actual=actual,
            contract=base_contract,
            viable_minimum=viable_minimum,
        )
    return {"chapter_gate_action": "review"}


def recover_chapter_length_contract(
    contract: ChapterLengthContract,
    *,
    accepted_characters: int,
    remaining_maximum_characters: int,
    book_minimum_characters: int,
) -> ChapterLengthContract:
    """Raise the current generation target when earlier chapters ran short.

    Detail owns the normal chapter target and its soft envelope. Text keeps
    those frozen bounds, but its rolling scene prompt must ask the current
    chapter to recover any deterministic deficit that would otherwise make
    the book minimum unreachable. The function never expands the frozen
    chapter maximum; an impossible deficit is still reported by the book
    budget gate after this best-effort generation.
    """

    required = (
        book_minimum_characters
        - accepted_characters
        - remaining_maximum_characters
    )
    if required <= contract.min_characters:
        return contract
    recovery_minimum = min(contract.max_characters, max(contract.min_characters, required))
    return contract.model_copy(
        update={
            "target_characters": contract.max_characters,
            "min_characters": recovery_minimum,
        }
    )


def recover_chapter_length_contract_for_state(
    executor: StageExecutor,
    state: NarrativeRunState,
    contract: ChapterLengthContract,
) -> ChapterLengthContract:
    """Apply the frozen whole-book deficit to the active chapter contract."""

    run_id = state["run_id"]
    active_number = int(state["active_chapter_number"])
    detail = executor.detail(state)
    if not 1 <= active_number <= len(detail.chapters):
        raise ValueError("Chapter recovery does not match the frozen Detail chapters")

    refs = state.get("chapter_version_refs") or {}
    accepted_characters = 0
    for chapter in detail.chapters[: active_number - 1]:
        version_id = refs.get(chapter.ref)
        if not version_id:
            raise ValueError(f"Missing accepted chapter version for {chapter.ref}")
        accepted = executor.chapters.read(run_id, chapter.ref, version_id).artifact
        accepted_characters += count_prose_characters(accepted.content)

    definition = executor.runs.definition(run_id)
    remaining_maximum = 0
    for chapter in detail.chapters[active_number:]:
        future = chapter_length_contract(
            chapter.target_characters,
            str(definition.quality_mode or "balanced"),
            scene_count=len(chapter.scenes),
        )
        if future is None:
            return contract
        remaining_maximum += future.max_characters
    book_minimum = minimum_viable_book_characters(definition.scale_profile)
    return recover_chapter_length_contract(
        contract,
        accepted_characters=accepted_characters,
        remaining_maximum_characters=remaining_maximum,
        book_minimum_characters=book_minimum,
    )


def _severe_underlength_blocker(
    executor: StageExecutor,
    state: NarrativeRunState,
    *,
    version_id: str,
    actual: int,
    contract: ChapterLengthContract,
    viable_minimum: int,
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    payload = {
        "code": "chapter_severely_underlength",
        "actual_characters": actual,
        "target_characters": contract.target_characters,
        "minimum_viable_characters": viable_minimum,
        "claim": "当前章节篇幅过短，正文可能尚未完整承载冻结细纲。",
        "evidence": (
            f"当前候选为 {actual} 字，低于最低可用篇幅 "
            f"{viable_minimum} 字。"
        ),
        "severity": "blocking",
    }
    executor.events.append(
        run_id,
        event_id=f"{run_id}:{chapter_id}:{version_id}:severely-underlength",
        type="quality.warning",
        stage_id="text",
        node_id="text.check_length_contract",
        chapter_id=chapter_id,
        status="warning",
        payload=payload,
        payload_ref=version_id,
    )
    return {
        "chapter_gate_action": "length_decision",
        "chapter_length_blocker": payload,
    }


def evaluate_book_length_budget(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    """Stop before review when the frozen book minimum is no longer reachable.

    Chapter and scene length drift remains a warning. This guard only fires
    when every remaining chapter landing at its own soft maximum would still
    leave the whole book below the frozen minimum. It therefore avoids
    spending more Provider calls on a mathematically impossible Run without
    turning ordinary short chapters into hard blockers.
    """

    run_id = state["run_id"]
    active_number = int(state["active_chapter_number"])
    detail = executor.detail(state)
    if not 1 <= active_number <= len(detail.chapters):
        raise ValueError("Book budget review does not match the frozen Detail chapters")

    active_id = state["active_chapter_id"]
    refs = state.get("chapter_version_refs") or {}
    current_ref = refs.get(active_id)
    if not current_ref:
        raise ValueError("Book budget review requires the active chapter candidate")
    current = executor.chapters.read(run_id, active_id, current_ref).artifact
    current_characters = count_prose_characters(current.content)

    accepted_characters = 0
    for chapter in detail.chapters[: active_number - 1]:
        version_id = refs.get(chapter.ref)
        if not version_id:
            raise ValueError(
                f"Book budget review is missing the accepted version for {chapter.ref}"
            )
        accepted = executor.chapters.read(run_id, chapter.ref, version_id).artifact
        accepted_characters += count_prose_characters(accepted.content)

    definition = executor.runs.definition(run_id)
    profile = definition.scale_profile
    remaining_target = 0
    remaining_minimum = 0
    remaining_maximum = 0
    for chapter in detail.chapters[active_number:]:
        contract = chapter_length_contract(
            chapter.target_characters,
            str(definition.quality_mode or "balanced"),
            scene_count=len(chapter.scenes),
        )
        if contract is None:
            # Without a frozen target we cannot prove that the book is
            # unreachable; retain the existing warning-only behavior.
            return {"chapter_gate_action": "review"}
        remaining_target += contract.target_characters
        remaining_minimum += contract.min_characters
        remaining_maximum += contract.max_characters

    # Keep the final whole-book gate authoritative for the last chapter. The
    # reachability guard is specifically an early diagnostic for a still-open
    # tail, not a replacement for the terminal aggregate check.
    if not detail.chapters[active_number:]:
        return {"chapter_gate_action": "review", "book_budget_blocker": {}}

    book_minimum = minimum_viable_book_characters(profile)
    _, book_maximum = soft_book_length_bounds(profile)
    projected_maximum = (
        accepted_characters + current_characters + remaining_maximum
    )
    if projected_maximum < book_minimum:
        payload = {
            "code": "book_length_budget_unreachable",
            "accepted_characters": accepted_characters,
            "current_chapter_characters": current_characters,
            "remaining_chapter_count": len(detail.chapters) - active_number,
            "remaining_target_characters": remaining_target,
            "remaining_minimum_characters": remaining_minimum,
            "remaining_maximum_characters": remaining_maximum,
            "projected_maximum_characters": projected_maximum,
            "book_minimum_characters": book_minimum,
            "book_target_characters": profile.word_target_soft,
            "book_maximum_characters": book_maximum,
            "claim": (
                "当前章节接受后，即使剩余章节全部达到各自软上限，"
                "全书仍无法达到最低可用篇幅。"
            ),
            "evidence": (
                f"当前累计上限推算为 {projected_maximum} 字，"
                f"低于全书最低可用篇幅 {book_minimum} 字。"
            ),
            "severity": "blocking",
        }
        executor.events.append(
            run_id,
            event_id=f"{run_id}:{active_id}:{current_ref}:book-budget-unreachable",
            type="quality.warning",
            stage_id="text",
            node_id="text.check_book_budget",
            chapter_id=active_id,
            status="warning",
            payload=payload,
            payload_ref=current_ref,
        )
        return {
            "chapter_gate_action": "budget_decision",
            "book_budget_blocker": payload,
        }
    return {"chapter_gate_action": "review", "book_budget_blocker": {}}


__all__ = [
    "evaluate_book_length_budget",
    "evaluate_chapter_length",
    "recover_chapter_length_contract",
    "recover_chapter_length_contract_for_state",
]
