from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.phase32_route_artifacts import (
    BeatBoardArtifact,
    BeatBoardBeat,
    BookDeliveryArtifact,
    BookArchitectureArtifact,
    ChapterArtifact,
    CharacterBibleArtifact,
    CharacterRecord,
    CharacterRelationship,
    DetailChapterPlan,
    DetailPlanIndexArtifact,
    DetailScenePlan,
    DetailWindow,
    CoverArtifact,
    CoverBrief,
    CoverCandidate,
    NovelBriefArtifact,
    PartContract,
    SceneDeckArtifact,
    SceneDeckScene,
    ScreenplayBlock,
    ScreenplayBriefArtifact,
    ScreenplayDraftArtifact,
    ScriptDeliveryArtifact,
    SectionPlanArtifact,
    SectionPlanUnit,
    ShortProseUnitArtifact,
    StoryMapAnchor,
    StoryMapArtifact,
    VolumeArchitectureArtifact,
    VolumeContract,
    bind_phase32_artifact,
    phase32_artifact_binding,
    validate_long_novel_hierarchy,
    validate_rolling_detail_references,
    validate_scene_contiguous_boundary,
    validate_scene_deck_references,
    validate_section_plan_references,
    validate_volume_architecture_references,
)


def _character(ref: str = "maya") -> CharacterRecord:
    return CharacterRecord(
        subject_ref=ref,
        display_name="Maya",
        role="档案记者",
        desire="找出被删去的真相",
        stakes="失去职业与家人的信任",
        constraints=("不能公开未核实的证据",),
        voice="短句，先核对事实再表达",
        arc_scope="从旁观者变成承担后果的人",
    )


def _brief(target_characters: int = 20_000) -> NovelBriefArtifact:
    return NovelBriefArtifact(
        title="失序档案",
        premise="一名记者追查一份被篡改的城市档案。",
        audience_promise="让读者看到真相代价，而不是只看到谜底。",
        theme_question="记录真相是否值得牺牲安全？",
        world_rules=("所有公共档案都有可追溯的签名。",),
        ending_direction="主角公开证据并接受由此带来的代价。",
        narrative_voice="克制、具体、贴近现场",
        target_characters=target_characters,
    )


def test_route_bindings_cover_planning_stages_without_legacy_modes() -> None:
    assert phase32_artifact_binding("screenplay_sample", "beat_board").artifact_kind == "beat_board"
    assert phase32_artifact_binding("short_novel", "story_map").artifact_kind == "story_map"
    assert phase32_artifact_binding("long_novel", "rolling_detail").artifact_kind == "detail_plan_index"
    assert phase32_artifact_binding("screenplay_sample", "script").artifact_kind == "screenplay_draft"
    assert phase32_artifact_binding("short_novel", "text").artifact_kind == "short_prose_unit"
    assert phase32_artifact_binding("long_novel", "text").artifact_kind == "chapter"
    assert phase32_artifact_binding("short_novel", "cover").artifact_kind == "cover"
    assert phase32_artifact_binding("long_novel", "export").artifact_kind == "book_delivery"
    with pytest.raises(ValueError, match="No Phase 32 Artifact"):
        phase32_artifact_binding("short_novel", "spine")


def test_novel_brief_applies_route_specific_soft_length_envelope() -> None:
    assert bind_phase32_artifact("short_novel", "brief", _brief(20_000))
    assert bind_phase32_artifact("long_novel", "brief", _brief(120_000))

    with pytest.raises(ValueError, match="between 100,000 and 1,000,000"):
        bind_phase32_artifact("long_novel", "brief", _brief(20_000))
    with pytest.raises(ValueError, match="between 2,000 and 130,000"):
        bind_phase32_artifact("short_novel", "brief", _brief(140_000))


@pytest.mark.parametrize("title", ("待定标题", "未命名作品", "screenplay_sample"))
def test_brief_rejects_placeholder_or_route_titles(title: str) -> None:
    with pytest.raises(ValidationError, match="formal work title"):
        ScreenplayBriefArtifact(
            title=title,
            sample_type="调查悬疑样片",
            target_minutes=12,
            premise="公共档案的签名链正在被抹除。",
            audience_promise="观众持续判断谁替换了签名页。",
            visible_conflict="主角必须在闭馆前取得原始签名页。",
            ending_effect="签名页进入听证记录，主角也暴露身份。",
            tone="冷峻、克制、证据驱动",
        )


def test_character_bible_requires_frozen_subject_refs_and_valid_edges() -> None:
    artifact = CharacterBibleArtifact(
        characters=(_character("maya"), _character("liang")),
        relationships=(
            CharacterRelationship(
                from_subject_ref="maya",
                to_subject_ref="liang",
                pressure="Maya needs Liang's access badge.",
                change_trigger="Liang discovers the missing archive entry.",
            ),
        ),
    )
    assert bind_phase32_artifact("short_novel", "cast", artifact) == artifact

    with pytest.raises(ValueError, match="unknown subject"):
        CharacterBibleArtifact(
            characters=(_character("maya"),),
            relationships=(
                CharacterRelationship(
                    from_subject_ref="maya",
                    to_subject_ref="ghost",
                    pressure="需要帮助。",
                    change_trigger="发现证据。",
                ),
            ),
        )


def test_screenplay_planning_refs_are_unique_and_strict() -> None:
    beat = BeatBoardBeat(
        beat_ref="beat-1",
        dramatic_job="让主角决定是否越权查档。",
        visible_pressure="档案室即将关闭。",
        character_decision="主角复制一份未授权记录。",
        outcome="她留下了可追查的证据。",
        timing_hint="约 90 秒",
    )
    assert BeatBoardArtifact(beats=(beat,))

    with pytest.raises(ValueError, match="Beat refs must be unique"):
        BeatBoardArtifact(beats=(beat, beat))

    with pytest.raises(ValidationError, match="extra"):
        BeatBoardBeat.model_validate({**beat.model_dump(), "provider": "deepseek"})


def test_scene_deck_accepts_visible_scene_contract_only() -> None:
    scene = SceneDeckScene(
        scene_ref="scene-1",
        heading="INT. 档案室 - NIGHT",
        location_and_time="市档案馆，闭馆前十分钟",
        cast_subject_refs=("maya",),
        visible_goal="找到被调换的签名页。",
        opposition="保安要求她离开。",
        outcome="她带走一张带水印的复印件。",
        soft_page_target=2.5,
    )
    assert bind_phase32_artifact(
        "screenplay_sample", "scene_deck", SceneDeckArtifact(scenes=(scene,))
    )
    cast = CharacterBibleArtifact(characters=(_character("maya"),))
    validate_scene_deck_references(SceneDeckArtifact(scenes=(scene,)), cast)

    with pytest.raises(ValueError, match="unique"):
        SceneDeckScene.model_validate(
            {**scene.model_dump(), "cast_subject_refs": ["maya", "maya"]}
        )
    with pytest.raises(ValueError, match="unknown Cast subjects"):
        validate_scene_deck_references(
            SceneDeckArtifact(
                scenes=(scene.model_copy(update={"cast_subject_refs": ("ghost",)}),)
            ),
            cast,
        )

    with pytest.raises(ValueError, match="one contiguous location and time"):
        validate_scene_contiguous_boundary(
            scene.model_copy(
                update={
                    "heading": "INT. 档案室/陈默家门口 - NIGHT",
                    "location_and_time": "档案室；随后陈默家门口",
                }
            )
        )


def test_screenplay_draft_requires_scene_heading_and_bound_dialogue() -> None:
    draft = ScreenplayDraftArtifact(
        scene_ref="scene-1",
        blocks=(
            ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
            ScreenplayBlock(kind="action", text="Maya 在关灯前翻开最后一页。"),
            ScreenplayBlock(
                kind="dialogue",
                text="这不是修订，是替换。",
                speaker_ref="maya",
            ),
        ),
    )
    assert bind_phase32_artifact("screenplay_sample", "script", draft)
    delivery = ScriptDeliveryArtifact(
        title="被删去的城市",
        author="",
        version_note="样片初稿",
        formats=("fountain", "pdf"),
        scene_refs=("scene-1",),
        scene_version_refs=("p32-script-committed-" + "a" * 64,),
    )
    assert bind_phase32_artifact("screenplay_sample", "export", delivery)

    with pytest.raises(ValueError, match="scene heading"):
        ScreenplayDraftArtifact(
            scene_ref="scene-1",
            blocks=(
                ScreenplayBlock(kind="action", text="Maya 走进档案室。"),
                ScreenplayBlock(kind="action", text="灯熄灭。"),
            ),
        )
    with pytest.raises(ValueError, match="speaker ref"):
        ScreenplayDraftArtifact(
            scene_ref="scene-1",
            blocks=(
                ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
                ScreenplayBlock(kind="dialogue", text="有人吗？"),
            ),
        )

    with pytest.raises(ValueError, match="exactly one frozen Scene heading"):
        ScreenplayDraftArtifact(
            scene_ref="scene-1",
            blocks=(
                ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
                ScreenplayBlock(kind="action", text="Maya 翻开最后一页。"),
                ScreenplayBlock(kind="scene_heading", text="INT. 走廊 - NIGHT"),
                ScreenplayBlock(kind="action", text="脚步声停在门外。"),
            ),
        )


def test_prose_chapter_cover_and_book_delivery_are_route_specific() -> None:
    short_text = ShortProseUnitArtifact(
        unit_ref="unit-1",
        unit_kind="section",
        title="签名链",
        pov_subject_ref="maya",
        content="Maya 先核对了签名，再把复印件放进证物袋。",
    )
    assert bind_phase32_artifact("short_novel", "text", short_text)

    chapter = ChapterArtifact(
        chapter_ref="chapter-1",
        volume_ref="volume-1",
        title="第一份证据",
        pov_subject_ref="maya",
        content="她在听证前一夜重新整理了每个时间戳。",
    )
    assert bind_phase32_artifact("long_novel", "text", chapter)

    cover = CoverArtifact(
        brief=CoverBrief(
            concept="冷色档案与一束被撕开的光",
            image_prompt="现代城市档案室，冷色胶片质感，单束顶光",
            palette=("深靛蓝", "银灰"),
        ),
        candidates=(
            CoverCandidate(
                asset_ref="asset-cover-1",
                alt_text="档案室中的单束顶光",
                visual_notes="主体留出标题安全区",
            ),
        ),
        selected_asset_ref="asset-cover-1",
    )
    assert bind_phase32_artifact("short_novel", "cover", cover)
    assert bind_phase32_artifact("long_novel", "cover", cover)

    delivery = BookDeliveryArtifact(
        title="被删去的城市",
        author="",
        version_note="第一版交付",
        formats=("epub", "markdown"),
        chapter_refs=("chapter-1",),
        chapter_version_refs=("p32-text-committed-" + "a" * 64,),
        volume_refs=("volume-1",),
        cover_asset_ref="asset-cover-1",
    )
    assert bind_phase32_artifact("long_novel", "export", delivery)

    with pytest.raises(ValueError, match="one of the candidates"):
        CoverArtifact.model_validate(
            {**cover.model_dump(), "selected_asset_ref": "asset-missing"}
        )


def test_story_map_and_section_plan_keep_ordered_refs() -> None:
    anchor = StoryMapAnchor(
        anchor_ref="anchor-1",
        dramatic_job="建立档案被篡改的压力。",
        pressure="关键记录在公开前消失。",
        choice_or_revelation="主角决定追查签名链。",
        consequence_or_open_effect="她被卷入机构内部调查。",
        promise_refs=("promise-signature-chain",),
    )
    story_map = StoryMapArtifact(
        opening_state="主角只相信公开档案。",
        story_question="谁在修改城市记忆？",
        anchors=(anchor,),
        ending_state="真相公开，但主角失去原职。",
    )
    assert bind_phase32_artifact("short_novel", "story_map", story_map)

    unit = SectionPlanUnit(
        unit_ref="unit-1",
        ordinal=1,
        title="签名链",
        dramatic_job="让调查获得第一条可验证线索。",
        pov_subject_ref="maya",
        scene_load="档案室与走廊两场短场景。",
        handoff="下一单元从复印件上的时间戳开始。",
        soft_character_budget=3_000,
        promise_refs=("promise-signature-chain",),
    )
    assert bind_phase32_artifact(
        "short_novel", "section_plan", SectionPlanArtifact(units=(unit,))
    )

    with pytest.raises(ValueError, match="contiguous"):
        SectionPlanArtifact(units=(unit.model_copy(update={"ordinal": 2}),))


def test_section_plan_references_committed_story_promises_and_cast() -> None:
    story_map = StoryMapArtifact(
        opening_state="主角只相信公开档案。",
        story_question="谁在修改城市记忆？",
        anchors=(
            StoryMapAnchor(
                anchor_ref="anchor-1",
                dramatic_job="建立档案被篡改的压力。",
                pressure="关键记录在公开前消失。",
                choice_or_revelation="主角决定追查签名链。",
                consequence_or_open_effect="她被卷入机构内部调查。",
                promise_refs=("promise-truth-cost",),
            ),
        ),
        ending_state="真相公开，但主角失去原职。",
    )
    cast = CharacterBibleArtifact(characters=(_character(),))
    unit = SectionPlanUnit(
        unit_ref="unit-1",
        ordinal=1,
        title="签名链",
        dramatic_job="让调查获得第一条可验证线索。",
        pov_subject_ref="maya",
        scene_load="档案室与走廊两场短场景。",
        handoff="下一单元从复印件上的时间戳开始。",
        soft_character_budget=3_000,
        promise_refs=("promise-truth-cost",),
    )
    section_plan = SectionPlanArtifact(units=(unit,))

    validate_section_plan_references(story_map, section_plan, cast)

    with pytest.raises(ValueError, match="must carry at least one Story Map promise ref"):
        validate_section_plan_references(
            story_map,
            SectionPlanArtifact(
                units=(unit.model_copy(update={"promise_refs": ()}),)
            ),
            cast,
        )

    with pytest.raises(ValueError, match="does not cover committed Story Map promises"):
        validate_section_plan_references(
            StoryMapArtifact(
                opening_state=story_map.opening_state,
                story_question=story_map.story_question,
                anchors=(
                    *story_map.anchors,
                    story_map.anchors[0].model_copy(
                        update={
                            "anchor_ref": "anchor-2",
                            "promise_refs": ("promise-uncovered",),
                        }
                    ),
                ),
                ending_state=story_map.ending_state,
            ),
            section_plan,
            cast,
        )

    with pytest.raises(ValueError, match="unknown Cast subjects"):
        validate_section_plan_references(
            story_map,
            SectionPlanArtifact(
                units=(unit.model_copy(update={"pov_subject_ref": "ghost"}),)
            ),
            cast,
        )
    with pytest.raises(ValueError, match="unknown Story Map promises"):
        validate_section_plan_references(
            story_map,
            SectionPlanArtifact(
                units=(unit.model_copy(update={"promise_refs": ("promise-ghost",)}),)
            ),
            cast,
        )


def test_long_novel_hierarchy_rejects_duplicate_or_overlapping_refs() -> None:
    part = PartContract(
        part_ref="part-1",
        ordinal=1,
        entry_state="主角开始调查。",
        dramatic_question="她愿意承担多大代价？",
        promise_refs=("promise-1",),
        turning_point_refs=("turn-1",),
        exit_state="她公开第一份证据。",
    )
    architecture = BookArchitectureArtifact(
        book_promise="一场关于城市记忆的长期调查。",
        ending_conditions=("证据链公开且主角承担后果。",),
        parts=(part,),
    )
    assert bind_phase32_artifact("long_novel", "book_architecture", architecture)

    volume = VolumeContract(
        volume_ref="volume-1",
        ordinal=1,
        part_ref="part-1",
        promise="找到第一份原始档案。",
        conflict="机构试图销毁备份。",
        climax="主角在听证会上提交证据。",
        closure="调查进入公众视野。",
        cast_subject_refs=("maya",),
        length_hint=40_000,
    )
    volumes = VolumeArchitectureArtifact(volumes=(volume,))
    assert bind_phase32_artifact("long_novel", "volumes", volumes)
    cast = CharacterBibleArtifact(characters=(_character("maya"),))
    validate_volume_architecture_references(architecture, volumes, cast)

    with pytest.raises(ValueError, match="unique"):
        VolumeContract.model_validate(
            {**volume.model_dump(), "cast_subject_refs": ["maya", "maya"]}
        )
    with pytest.raises(ValueError, match="unknown Cast subjects"):
        validate_volume_architecture_references(
            architecture,
            VolumeArchitectureArtifact(
                volumes=(
                    volume.model_copy(update={"cast_subject_refs": ("ghost",)}),
                )
            ),
            cast,
        )

    window = DetailWindow(
        window_ref="window-1",
        ordinal=1,
        volume_refs=("volume-1",),
        chapters=(
            DetailChapterPlan(
                chapter_ref="chapter-1",
                ordinal=1,
                volume_ref="volume-1",
                title="第一份证据",
                pov_subject_ref="maya",
                cast_subject_refs=("maya",),
                dramatic_job="让主角拿到可以独立核验的第一份证据。",
                entry_state="主角只有一张来源不明的复印件。",
                scenes=(
                    DetailScenePlan(
                        scene_ref="scene-chapter-1-archive",
                        ordinal=1,
                        location="市档案馆修复室",
                        time_context="闭馆前十分钟",
                        cast_subject_refs=("maya",),
                        goal="核对复印件的纸张水印。",
                        opposition="值班员要求她立刻离开。",
                        outcome="她确认复印件来自已封存的原始卷宗。",
                    ),
                ),
                conflict="离馆期限与证据核验互相冲突。",
                stakes="失败会让复印件失去公开价值。",
                exit_state="主角掌握了可追溯到原卷宗的水印证据。",
                hook="水印日期晚于档案宣称的封存日期。",
                handoff="下一章从追查异常封存日期开始。",
                length_hint=3_000,
            ),
            DetailChapterPlan(
                chapter_ref="chapter-2",
                ordinal=2,
                volume_ref="volume-1",
                title="封存日期",
                pov_subject_ref="maya",
                cast_subject_refs=("maya",),
                dramatic_job="把纸面异常推进为需要公开回应的制度冲突。",
                entry_state="主角掌握异常水印日期。",
                scenes=(
                    DetailScenePlan(
                        scene_ref="scene-chapter-2-hearing",
                        ordinal=1,
                        location="市政听证准备室",
                        time_context="听证会前一小时",
                        cast_subject_refs=("maya",),
                        goal="让记录员把异常日期写入正式议程。",
                        opposition="主持人以来源不明为由拒绝登记。",
                        outcome="主角公开自己的取证过程换取临时登记。",
                    ),
                ),
                conflict="证据可信度与主角的职业安全发生冲突。",
                stakes="公开取证过程可能让她失去原职。",
                exit_state="异常日期进入正式议程，主角的违规取证同时曝光。",
                hook="有人在议程发布前撤回了原始封存单。",
                handoff="下一窗口进入公开听证与证人保护。",
                length_hint=3_500,
            ),
        ),
        entry_state="主角拿到复印件。",
        handoff="下一窗口进入听证准备。",
        next_window_entry_state="公众开始关注调查。",
    )
    assert bind_phase32_artifact(
        "long_novel", "rolling_detail", DetailPlanIndexArtifact(windows=(window,))
    )

    with pytest.raises(ValueError, match="unique across windows"):
        DetailPlanIndexArtifact(
            windows=(
                window,
                window.model_copy(
                    update={"window_ref": "window-2", "ordinal": 2}
                ),
            )
        )

    with pytest.raises(ValueError, match="Scene refs must be unique"):
        DetailPlanIndexArtifact(
            windows=(
                window.model_copy(
                    update={
                        "chapters": (
                            window.chapters[0],
                            window.chapters[1].model_copy(
                                update={"scenes": window.chapters[0].scenes}
                            ),
                        )
                    }
                ),
            )
        )

    with pytest.raises(ValueError, match="Chapter volume refs must match"):
        DetailWindow(
            **{
                **window.model_dump(),
                "chapters": [
                    {
                        **window.chapters[0].model_dump(),
                        "volume_ref": "volume-ghost",
                    }
                ],
            }
        )

    detail = DetailPlanIndexArtifact(windows=(window,))
    validate_long_novel_hierarchy(architecture, volumes, detail, cast)
    validate_rolling_detail_references(volumes, detail, cast)
    with pytest.raises(ValueError, match="unknown Parts"):
        validate_long_novel_hierarchy(
            architecture,
            VolumeArchitectureArtifact(
                volumes=(volume.model_copy(update={"part_ref": "part-ghost"}),)
            ),
            detail,
            cast,
        )
    with pytest.raises(ValueError, match="unknown Volumes"):
        validate_rolling_detail_references(
            volumes,
            DetailPlanIndexArtifact(
                windows=(
                    window.model_copy(
                        update={
                            "volume_refs": ("volume-ghost",),
                            "chapters": (
                                window.chapters[0].model_copy(
                                    update={"volume_ref": "volume-ghost"}
                                ),
                            ),
                        }
                    ),
                )
            ),
            cast,
        )
    with pytest.raises(ValueError, match="unknown Cast subjects"):
        validate_rolling_detail_references(
            volumes,
            DetailPlanIndexArtifact(
                windows=(
                    window.model_copy(
                        update={
                            "chapters": (
                                window.chapters[0].model_copy(
                                    update={
                                        "pov_subject_ref": "ghost",
                                        "cast_subject_refs": ("ghost",),
                                        "scenes": (
                                            window.chapters[0].scenes[0].model_copy(
                                                update={"cast_subject_refs": ("ghost",)}
                                            ),
                                        ),
                                    }
                                ),
                            )
                        }
                    ),
                )
            ),
            cast,
        )


def test_cross_route_artifact_type_is_rejected() -> None:
    scene = SceneDeckArtifact(
        scenes=(
            SceneDeckScene(
                scene_ref="scene-1",
                heading="INT. 档案室 - NIGHT",
                location_and_time="闭馆前",
                cast_subject_refs=("maya",),
                visible_goal="找到证据。",
                opposition="保安阻拦。",
                outcome="主角拿到复印件。",
                soft_page_target=1,
            ),
        )
    )
    with pytest.raises(ValueError, match="does not match"):
        bind_phase32_artifact("short_novel", "story_map", scene)


def test_phase32_artifact_module_remains_isolated_from_legacy_runtime_contracts() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/output_contracts/phase32_route_artifacts.py"
    ).read_text(encoding="utf-8")
    assert "artifacts_vnext" not in source
    assert "quality_mode" not in source
    assert "STAGE_ORDER" not in source
    assert "novel_workflow.runtime" not in source
