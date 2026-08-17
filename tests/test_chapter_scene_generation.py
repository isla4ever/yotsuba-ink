from __future__ import annotations

import json

from novel_workflow.output_contracts.artifacts_vnext import (
    ContextManifest,
    DetailChapter,
)
from novel_workflow.runtime.graph.chapter_scene_generation import (
    build_scene_manifest,
    scene_length_warning_payload,
)
from novel_workflow.runtime.graph.chapter_scene_facts import (
    introduced_quantified_fact_tokens,
)
from novel_workflow.runtime.graph.chapter_scene_length import (
    allocate_scene_length_contracts,
    next_scene_length_contract,
)
from novel_workflow.runtime.graph.context_compiler import (
    _context_snippet,
    _manifest_hash,
)
from novel_workflow.workflows.narrative_scale import chapter_length_contract


def test_scene_budgets_are_flexible_instead_of_equal_hard_splits() -> None:
    chapter = chapter_length_contract(2_500, "balanced", scene_count=2)
    assert chapter is not None

    scenes = allocate_scene_length_contracts(chapter)

    assert [item.target_characters for item in scenes] == [1_250, 1_250]
    assert scenes[0].min_characters == 812
    assert scenes[0].max_characters == 1_688
    assert scenes[0].min_characters < chapter.min_characters // 2
    assert scenes[0].max_characters > chapter.max_characters // 2


def test_small_scene_length_drift_is_a_warning_without_changing_chapter_envelope() -> None:
    chapter = chapter_length_contract(2_500, "balanced", scene_count=2)
    assert chapter is not None

    first = next_scene_length_contract(chapter, accepted_character_counts=[])
    warning = scene_length_warning_payload(first, 1_739)

    assert warning == {
        "code": "scene_length_soft_band",
        "actual_characters": 1_739,
        "target_characters": 1_250,
        "soft_bounds": [812, 1_688],
    }
    assert chapter.min_characters == 2_050
    assert chapter.max_characters == 2_950
    assert chapter.target_characters == 2_500


def test_later_scene_inherits_the_exact_remaining_chapter_budget() -> None:
    chapter = chapter_length_contract(2_500, "balanced", scene_count=2)
    assert chapter is not None

    second = next_scene_length_contract(
        chapter,
        accepted_character_counts=[911],
    )

    assert second.target_characters == 1_589
    assert second.min_characters == 1_139
    assert second.max_characters == 2_039
    assert 911 + second.target_characters == chapter.target_characters
    assert 911 + second.min_characters == chapter.min_characters
    assert 911 + second.max_characters == chapter.max_characters


def test_scene_manifest_keeps_world_rules_and_scopes_revision_to_one_scene() -> None:
    chapter = _detail_chapter()
    chapter_contract = chapter_length_contract(2_500, "balanced", scene_count=2)
    assert chapter_contract is not None
    scene_contract = next_scene_length_contract(
        chapter_contract,
        accepted_character_counts=[911],
    )

    manifest = build_scene_manifest(
        _base_manifest(chapter),
        detail_chapter=chapter,
        scene_index=2,
        contract=scene_contract,
        output_tokens=2_100,
        previous_scene="第一场结尾已形成异常哈希。",
        source_scene="过短旧稿",
        revision_direction="只扩写当前场景，不新增事实。",
    )

    refs = {snippet.ref: snippet for snippet in manifest.snippets}
    assert manifest.required == [
        "detail.chapter",
        "cast.subjects",
        "volume.contract",
        "brief.world_rules",
        "scene.execution",
        "scale.scene_length",
    ]
    assert "current_chapter.previous_scene" in manifest.optional
    assert manifest.optional[-2:] == ["revision.source_draft", "revision.request"]
    script = json.loads(refs["detail.chapter"].text)
    assert script["scene_index"] == 2
    assert script["scene"] == chapter.scenes[1].model_dump(mode="json")
    assert script["chapter_handoff"] == chapter.handoff
    assert json.loads(refs["revision.source_draft"].text) == {
        "scope": "scene",
        "measured_non_whitespace_characters": 4,
        "content": "过短旧稿",
    }
    length = json.loads(refs["scale.scene_length"].text)
    assert length["target_characters"] == 1_589
    assert length["accepted_prior_characters"] == 911
    assert length["chapter_min_characters"] == 2_050
    assert length["chapter_max_characters"] == 2_950
    assert manifest.budget.output_tokens == 2_100


def test_quantified_fact_gate_rejects_only_values_absent_from_frozen_context() -> None:
    chapter = _detail_chapter()
    chapter_contract = chapter_length_contract(2_500, "balanced", scene_count=2)
    assert chapter_contract is not None
    manifest = build_scene_manifest(
        _base_manifest(chapter),
        detail_chapter=chapter,
        scene_index=1,
        contract=next_scene_length_contract(
            chapter_contract,
            accepted_character_counts=[],
        ),
        output_tokens=2_100,
    )

    assert introduced_quantified_fact_tokens(
        "她复核第三枚晶片，进度达到百分之六十七，又跳到81%。",
        manifest,
    ) == ("第三枚", "百分之六十七", "81%")
    assert introduced_quantified_fact_tokens(
        "她第一次复核没有结果，第二次才确认异常。",
        manifest,
    ) == ()
    assert introduced_quantified_fact_tokens(
        "她提前修复第二枚晶片。",
        manifest,
    ) == ("第二枚",)
    assert introduced_quantified_fact_tokens(
        "她按两段既定场景继续推进。",
        manifest,
    ) == ()


def _detail_chapter() -> DetailChapter:
    return DetailChapter.model_validate(
        {
            "ref": "chapter-1",
            "volume_ref": "volume-1",
            "title": "异常哈希",
            "target_characters": 2_500,
            "turn_refs": ["turn-1"],
            "purpose": "林澈修复异常晶片",
            "pov": "subject-1",
            "cast_ids": ["subject-1"],
            "scenes": [
                {
                    "place": "盐库修复间",
                    "objective": "执行哈希校验",
                    "conflict": "系统判定为空白但哈希不符",
                    "turn": "林澈尝试修复",
                    "result": "听见疑似弟弟的求救声",
                },
                {
                    "place": "盐库修复间",
                    "objective": "核对晶片与操作日志",
                    "conflict": "声音消失且晶片恢复空白",
                    "turn": "林澈固定哈希、签名和时间戳",
                    "result": "异常日志成为后续调查入口",
                },
            ],
            "handoff": "深夜，林澈留在修复间并决定追查晶片来源。",
        }
    )


def _base_manifest(chapter: DetailChapter) -> ContextManifest:
    snippets = [
        _context_snippet("detail.chapter", "chapter_script", chapter.model_dump(mode="json")),
        _context_snippet("cast.subjects", "pov_scene_and_referenced_subjects", [{"id": "subject-1"}]),
        _context_snippet(
            "volume.contract",
            "local_promise_and_closure",
            {"id": "volume-1", "climax": "林澈修复第二枚晶片"},
        ),
        _context_snippet("brief.world_rules", "frozen_world_and_professional_rules", ["修复必须留痕"]),
        _context_snippet("brief.voice", "narrative_voice_contract", "冷峻克制"),
    ]
    body = {
        "task": chapter.ref,
        "required": [
            "detail.chapter",
            "cast.subjects",
            "volume.contract",
            "brief.world_rules",
        ],
        "optional": ["brief.voice"],
        "forbidden": ["full_canon"],
        "snippets": snippets,
        "budget": {
            "input_chars": sum(len(item["text"]) for item in snippets),
            "output_tokens": 6_000,
        },
    }
    body["manifest_hash"] = _manifest_hash(body)
    return ContextManifest.model_validate(body)
