"""Screenplay and short-novel Story Bible entry builders."""

from __future__ import annotations

from novel_workflow.output_contracts.phase32_route_artifacts import (
    BeatBoardArtifact,
    SceneDeckArtifact,
    SectionPlanArtifact,
    StoryMapArtifact,
)
from novel_workflow.storage.phase32_story_bible_entries import append_promises, entry


def project_screenplay(sections, beat_record, scene_record) -> None:
    promise_sources: dict[str, list[str]] = {}
    if beat_record is not None:
        artifact = BeatBoardArtifact.model_validate(beat_record.payload)
        for index, beat in enumerate(artifact.beats, start=1):
            sections["structure"].append(
                entry(
                    beat_record,
                    source_path=f"beat_board.beats[{index - 1}]",
                    entry_ref=beat.beat_ref,
                    kind="beat",
                    title=beat.dramatic_job,
                    body=beat.visible_pressure,
                    detail=f"决定：{beat.character_decision}\n结果：{beat.outcome}",
                    status="committed",
                    ordinal=index,
                    promise_refs=beat.setup_or_payoff_refs,
                    tags=(beat.timing_hint,),
                )
            )
            for promise_ref in beat.setup_or_payoff_refs:
                promise_sources.setdefault(promise_ref, []).append(beat.beat_ref)
        for index, beat in enumerate(artifact.beats, start=1):
            sections["continuity"].append(
                entry(
                    beat_record,
                    source_path=f"beat_board.beats[{index - 1}].outcome",
                    entry_ref=f"handoff:{beat.beat_ref}",
                    kind="handoff",
                    title=f"{beat.beat_ref} 的结果",
                    body=beat.outcome,
                    detail=beat.character_decision,
                    status="planned",
                    ordinal=index,
                    promise_refs=beat.setup_or_payoff_refs,
                )
            )
    if scene_record is not None:
        artifact = SceneDeckArtifact.model_validate(scene_record.payload)
        for index, scene in enumerate(artifact.scenes, start=1):
            sections["structure"].append(
                entry(
                    scene_record,
                    source_path=f"scene_deck.scenes[{index - 1}]",
                    entry_ref=scene.scene_ref,
                    kind="scene",
                    title=scene.heading,
                    body=scene.visible_goal,
                    detail=f"对抗：{scene.opposition}\n结果：{scene.outcome}",
                    status="committed",
                    ordinal=index,
                    subject_refs=scene.cast_subject_refs,
                    tags=(scene.location_and_time, f"{scene.soft_page_target:g} 页"),
                )
            )
    append_promises(sections["continuity"], beat_record, promise_sources)


def project_short_novel(sections, map_record, plan_record) -> None:
    promise_sources: dict[str, list[str]] = {}
    if map_record is not None:
        artifact = StoryMapArtifact.model_validate(map_record.payload)
        sections["continuity"].append(
            entry(
                map_record,
                source_path="story_map.opening_state",
                entry_ref="story-opening-state",
                kind="handoff",
                title="开场状态",
                body=artifact.opening_state,
                detail=artifact.story_question,
                status="planned",
                ordinal=1,
            )
        )
        for index, anchor in enumerate(artifact.anchors, start=1):
            sections["structure"].append(
                entry(
                    map_record,
                    source_path=f"story_map.anchors[{index - 1}]",
                    entry_ref=anchor.anchor_ref,
                    kind="story_anchor",
                    title=anchor.dramatic_job,
                    body=anchor.pressure,
                    detail=(
                        f"选择/揭示：{anchor.choice_or_revelation}\n"
                        f"后果：{anchor.consequence_or_open_effect}"
                    ),
                    status="committed",
                    ordinal=index,
                    promise_refs=anchor.promise_refs,
                )
            )
            for promise_ref in anchor.promise_refs:
                promise_sources.setdefault(promise_ref, []).append(anchor.anchor_ref)
        for index, question in enumerate(artifact.open_questions, start=1):
            sections["continuity"].append(
                entry(
                    map_record,
                    source_path=f"story_map.open_questions[{index - 1}]",
                    entry_ref=f"open-question-{index}",
                    kind="open_question",
                    title=f"开放问题 {index:02d}",
                    body=question,
                    status="open",
                    ordinal=index,
                )
            )
        sections["continuity"].append(
            entry(
                map_record,
                source_path="story_map.ending_state",
                entry_ref="story-ending-state",
                kind="ending_condition",
                title="收束状态",
                body=artifact.ending_state,
                status="planned",
            )
        )
    if plan_record is not None:
        artifact = SectionPlanArtifact.model_validate(plan_record.payload)
        for index, unit in enumerate(artifact.units, start=1):
            sections["structure"].append(
                entry(
                    plan_record,
                    source_path=f"section_plan.units[{index - 1}]",
                    entry_ref=unit.unit_ref,
                    kind="section_unit",
                    title=unit.title,
                    body=unit.dramatic_job,
                    detail=unit.scene_load,
                    status="committed",
                    ordinal=unit.ordinal,
                    subject_refs=(unit.pov_subject_ref,),
                    promise_refs=unit.promise_refs,
                    tags=(f"软预算 {unit.soft_character_budget:,} 字符",),
                )
            )
            sections["continuity"].append(
                entry(
                    plan_record,
                    source_path=f"section_plan.units[{index - 1}].handoff",
                    entry_ref=f"handoff:{unit.unit_ref}",
                    kind="handoff",
                    title=f"{unit.title} · 交接",
                    body=unit.handoff,
                    status="planned",
                    ordinal=unit.ordinal,
                    subject_refs=(unit.pov_subject_ref,),
                    promise_refs=unit.promise_refs,
                )
            )
            for promise_ref in unit.promise_refs:
                promise_sources.setdefault(promise_ref, []).append(unit.unit_ref)
    append_promises(sections["continuity"], map_record or plan_record, promise_sources)


__all__ = ["project_screenplay", "project_short_novel"]
