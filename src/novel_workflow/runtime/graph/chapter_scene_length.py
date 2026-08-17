from __future__ import annotations

import math
from dataclasses import dataclass

from novel_workflow.workflows.narrative_scale import ChapterLengthContract


_SCENE_FLEX_PERCENT = 35


@dataclass(frozen=True, slots=True)
class SceneLengthContract:
    scene_index: int
    scene_count: int
    target_characters: int
    min_characters: int
    max_characters: int
    accepted_prior_characters: int
    remaining_scene_count: int
    chapter_target_characters: int
    chapter_min_characters: int
    chapter_max_characters: int


def allocate_scene_length_contracts(
    chapter: ChapterLengthContract,
) -> tuple[SceneLengthContract, ...]:
    """Project rolling contracts when every scene lands on its current target."""

    contracts: list[SceneLengthContract] = []
    accepted: list[int] = []
    while len(contracts) < chapter.scene_count:
        contract = next_scene_length_contract(
            chapter,
            accepted_character_counts=accepted,
        )
        contracts.append(contract)
        accepted.append(contract.target_characters)
    return tuple(contracts)


def next_scene_length_contract(
    chapter: ChapterLengthContract,
    *,
    accepted_character_counts: list[int] | tuple[int, ...],
) -> SceneLengthContract:
    """Derive one flexible scene envelope from the chapter's remaining budget.

    Scene length follows dramatic load. The current bounds only restrict it
    enough that untouched scenes can still land the chapter inside its frozen
    hard envelope.
    """

    accepted = tuple(accepted_character_counts)
    if len(accepted) >= chapter.scene_count:
        raise ValueError("All frozen scenes already have accepted prose")
    if any(value < 1 for value in accepted):
        raise ValueError("Accepted scene character counts must be positive")

    scene_index = len(accepted) + 1
    remaining_scene_count = chapter.scene_count - scene_index
    accepted_prior = sum(accepted)
    scenes_including_current = remaining_scene_count + 1
    chapter_average = chapter.target_characters / chapter.scene_count
    flexible_minimum = max(
        1,
        math.floor(chapter_average * (100 - _SCENE_FLEX_PERCENT) / 100),
    )
    flexible_maximum = max(
        flexible_minimum,
        math.ceil(chapter_average * (100 + _SCENE_FLEX_PERCENT) / 100),
    )

    if remaining_scene_count == 0:
        minimum = max(1, chapter.min_characters - accepted_prior)
        maximum = chapter.max_characters - accepted_prior
    else:
        minimum = max(
            flexible_minimum,
            chapter.min_characters
            - accepted_prior
            - remaining_scene_count * flexible_maximum,
        )
        maximum = min(
            flexible_maximum,
            chapter.max_characters
            - accepted_prior
            - remaining_scene_count * flexible_minimum,
        )
    if maximum < minimum:
        raise ValueError("Accepted scene lengths leave no valid chapter completion budget")

    target = round(
        (chapter.target_characters - accepted_prior) / scenes_including_current
    )
    target = min(maximum, max(minimum, target))
    return SceneLengthContract(
        scene_index=scene_index,
        scene_count=chapter.scene_count,
        target_characters=target,
        min_characters=minimum,
        max_characters=maximum,
        accepted_prior_characters=accepted_prior,
        remaining_scene_count=remaining_scene_count,
        chapter_target_characters=chapter.target_characters,
        chapter_min_characters=chapter.min_characters,
        chapter_max_characters=chapter.max_characters,
    )


__all__ = [
    "SceneLengthContract",
    "allocate_scene_length_contracts",
    "next_scene_length_contract",
]
