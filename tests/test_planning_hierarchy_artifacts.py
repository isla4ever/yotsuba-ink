import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.planning_hierarchy import (
    DetailChapterUnitArtifact,
    DetailPlanIndexArtifact,
    DetailWindowArtifact,
    PartArcArtifact,
    PartTurnArtifact,
    StorySpineRootArtifact,
    VolumeArchitectureRootArtifact,
    VolumeUnitArtifact,
    mint_stable_ref,
    validate_stable_ref,
)
from novel_workflow.output_contracts.planning_hierarchy_validation import (
    validate_detail_aggregate,
    validate_spine_aggregate,
    validate_volume_aggregate,
)


def ref(kind: str, seed: str) -> str:
    return mint_stable_ref(kind, seed)  # type: ignore[arg-type]


def spine_root(part_refs: list[str], turn_refs: list[str]) -> StorySpineRootArtifact:
    milestones = (
        "inciting",
        "commitment",
        "midpoint_reversal",
        "crisis",
        "climax",
        "aftermath",
    )
    return StorySpineRootArtifact(
        book_promise="The investigation changes the family's understanding of responsibility.",
        book_milestones=[
            {"milestone": milestone, "turn_ref": turn_refs[min(index, len(turn_refs) - 1)]}
            for index, milestone in enumerate(milestones)
        ],
        part_refs=part_refs,
        ending="The final choice resolves the central promise at a visible cost.",
        open_questions=[],
    )


def part(seed: str, ordinal: int, turns: list[str]) -> PartArcArtifact:
    return PartArcArtifact(
        id=ref("part", seed),
        display_ordinal=ordinal,
        title=f"Part {ordinal}",
        entry_state="The investigation begins from a known but unstable state.",
        promise="The local promise must remain active.",
        climax="The local climax forces a costly choice.",
        exit_state="The Part hands forward a changed relationship and evidence state.",
        carried_questions=[],
        turn_refs=turns,
    )


def turn(seed: str, part_ref: str, ordinal: int) -> PartTurnArtifact:
    return PartTurnArtifact(
        id=seed if seed.startswith("turn-") else ref("turn", seed),
        part_ref=part_ref,
        display_ordinal=ordinal,
        cause="A visible decision changes the investigation.",
        change="The available evidence and relationship pressure change.",
        progress_type="information",
    )


def volume(
    seed: str,
    part_ref: str,
    turns: list[str],
    ordinal: int,
) -> VolumeUnitArtifact:
    return VolumeUnitArtifact(
        id=ref("volume", seed),
        part_ref=part_ref,
        display_ordinal=ordinal,
        title=f"Volume {ordinal}",
        promise="The volume promise tightens the investigation.",
        conflict="The volume conflict blocks the obvious answer.",
        climax="The final turn changes the family cost.",
        climax_turn_ref=turns[-1],
        closure="The next volume inherits a changed responsibility.",
        turn_refs=turns,
        cast_refs=["subject-protagonist"],
        length_hint="medium",
    )


def chapter(
    seed: str,
    window_ref: str,
    volume_ref: str,
    ordinal: int,
) -> DetailChapterUnitArtifact:
    return DetailChapterUnitArtifact(
        id=ref("chapter", seed),
        detail_window_ref=window_ref,
        volume_ref=volume_ref,
        display_ordinal=ordinal,
        title=f"Chapter {ordinal}",
        turn_refs=[ref("turn", f"turn-{ordinal}")],
        purpose="The chapter makes a visible choice under pressure.",
        pov_ref="subject-protagonist",
        cast_refs=["subject-protagonist"],
        scene_summaries=["The decision changes the immediate state."],
        handoff="The final state is explicit for the next chapter.",
    )


def test_stable_refs_are_not_ordinal_identity_and_survive_reordering() -> None:
    first = ref("part", "first premise")
    second = ref("part", "second premise")
    milestone_turn = ref("turn", "book milestone")
    root = spine_root([first, second], [milestone_turn])
    reordered = spine_root([second, first], [milestone_turn])

    assert reordered.part_refs == [second, first]
    assert first == ref("part", "first premise")
    assert second == ref("part", "second premise")


@pytest.mark.parametrize(
    "model, payload",
    [
        (
            PartArcArtifact,
            {
                "id": "part-123",
                "display_ordinal": 1,
                "title": "Part",
                "entry_state": "entry",
                "promise": "promise",
                "climax": "climax",
                "exit_state": "exit",
                "turn_refs": ["turn-story"],
            },
        ),
    ],
)
def test_ordinal_only_planning_ids_are_rejected(model, payload) -> None:
    with pytest.raises(ValidationError, match="stable|ordinal"):
        model.model_validate(payload)


@pytest.mark.parametrize("kind", ["part", "turn", "volume", "chapter", "window"])
def test_every_planning_ref_kind_rejects_ordinal_only_identity(kind: str) -> None:
    with pytest.raises(ValueError, match="ordinal"):
        validate_stable_ref(f"{kind}-123", kind)  # type: ignore[arg-type]


def test_spine_aggregate_rejects_missing_or_cross_part_turns() -> None:
    part_ref = ref("part", "part-a")
    turn_one = ref("turn", "turn-one")
    turn_two = ref("turn", "turn-two")
    root = spine_root([part_ref], [turn_one, turn_two])
    arc = part("part-a", 1, [turn_one, turn_two])

    with pytest.raises(ValueError, match="missing turn"):
        validate_spine_aggregate(root, [arc], [turn(turn_one, part_ref, 1)])

    with pytest.raises(ValueError, match="different Part"):
        validate_spine_aggregate(
            root,
            [arc],
            [
                turn(turn_one, part_ref, 1),
                turn(turn_two, ref("part", "other"), 2),
            ],
        )


def test_volume_aggregate_rejects_missing_and_duplicate_turn_coverage() -> None:
    part_ref = ref("part", "part-a")
    turn_one = ref("turn", "turn-one")
    turn_two = ref("turn", "turn-two")
    volume_one = ref("volume", "volume-one")
    volume_two = ref("volume", "volume-two")
    spine = spine_root([part_ref], [turn_one, turn_two])
    arc = part("part-a", 1, [turn_one, turn_two])
    root = VolumeArchitectureRootArtifact(
        part_refs=[part_ref],
        volume_refs=[volume_one, volume_two],
        part_volume_order={part_ref: [volume_one, volume_two]},
    )
    validate_volume_aggregate(
        spine,
        root,
        [arc],
        [
            volume("volume-one", part_ref, [turn_one], 1),
            volume("volume-two", part_ref, [turn_two], 2),
        ],
    )

    with pytest.raises(ValueError, match="coverage"):
        validate_volume_aggregate(
            spine,
            root,
            [arc],
            [volume("volume-one", part_ref, [turn_one], 1), volume("volume-two", part_ref, [turn_one], 2)],
        )

    with pytest.raises(ValueError, match="coverage"):
        validate_volume_aggregate(
            spine,
            root,
            [arc],
            [
                volume("volume-one", part_ref, [turn_one], 1),
                volume("volume-two", part_ref, [turn_two, turn_one], 2),
            ],
        )


def test_detail_aggregate_rejects_gaps_overlaps_and_unknown_volumes() -> None:
    volume_ref = ref("volume", "volume-one")
    unknown_volume_ref = ref("volume", "volume-unknown")
    window_ref = ref("window", "window-one")
    chapter_one = ref("chapter", "chapter-one")
    chapter_two = ref("chapter", "chapter-two")
    index = DetailPlanIndexArtifact(
        volume_refs=[volume_ref],
        chapter_order=[chapter_one, chapter_two],
        volume_chapter_order={volume_ref: [chapter_one, chapter_two]},
        window_order=[window_ref],
    )
    window = DetailWindowArtifact(
        id=window_ref,
        start_chapter_ref=chapter_one,
        end_chapter_ref=chapter_two,
        source_part_refs=[ref("part", "part-a")],
        source_volume_refs=[volume_ref],
        chapter_refs=[chapter_one, chapter_two],
        entry_handoff="The window starts from a known state.",
        exit_handoff="The window ends with a changed state.",
    )
    chapters = [
        chapter("chapter-one", window_ref, volume_ref, 1),
        chapter("chapter-two", window_ref, volume_ref, 2),
    ]
    validate_detail_aggregate(index, [window], chapters)

    gap = window.model_copy(update={"chapter_refs": [chapter_one]})
    with pytest.raises(ValueError, match="gap|overlap"):
        validate_detail_aggregate(index, [gap], chapters)

    second_window_ref = ref("window", "window-two")
    overlap_index = index.model_copy(
        update={"window_order": [window_ref, second_window_ref]}
    )
    overlap = DetailWindowArtifact(
        id=second_window_ref,
        start_chapter_ref=chapter_two,
        end_chapter_ref=chapter_two,
        source_part_refs=[ref("part", "part-a")],
        source_volume_refs=[volume_ref],
        chapter_refs=[chapter_two],
        entry_handoff="The second window starts from a known state.",
        exit_handoff="The second window ends with a changed state.",
    )
    with pytest.raises(ValueError, match="gap|overlap"):
        validate_detail_aggregate(overlap_index, [window, overlap], chapters)

    unknown = window.model_copy(update={"source_volume_refs": [unknown_volume_ref]})
    with pytest.raises(ValueError, match="unknown Volume"):
        validate_detail_aggregate(index, [unknown], chapters)
