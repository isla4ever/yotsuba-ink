from __future__ import annotations

import json

from novel_workflow.output_contracts.artifacts_vnext import (
    ContextManifest,
    DetailChapter,
)
from novel_workflow.runtime.graph.chapter_scene_contract_execution import (
    build_scene_fact_repair_manifest,
)
from novel_workflow.runtime.graph.chapter_scene_generation import (
    build_scene_manifest,
    scene_length_warning_payload,
)
from novel_workflow.runtime.graph.chapter_scene_facts import (
    apply_quantified_fact_repair,
    introduced_persistent_fact_violations,
    introduced_quantified_fact_tokens,
    quantified_fact_repair_window,
)
from novel_workflow.runtime.graph.chapter_scene_length import (
    allocate_scene_length_contracts,
    next_scene_length_contract,
)
from novel_workflow.runtime.graph.chapter_length import recover_chapter_length_contract
from novel_workflow.runtime.graph.context_compiler import (
    _context_snippet,
    _manifest_hash,
)
from novel_workflow.workflows.narrative_scale import (
    NarrativeScaleProfile,
    chapter_length_contract,
    minimum_viable_book_characters,
    minimum_viable_chapter_characters,
)


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


def test_book_recovery_raises_only_the_current_target_inside_frozen_maximum() -> None:
    chapter = chapter_length_contract(2_500, "fast", scene_count=2)
    assert chapter is not None

    recovered = recover_chapter_length_contract(
        chapter,
        accepted_characters=39_000,
        remaining_maximum_characters=3_500,
        book_minimum_characters=45_000,
    )

    assert recovered.target_characters == chapter.max_characters
    assert recovered.min_characters == 2_500
    assert recovered.max_characters == chapter.max_characters


def test_book_recovery_does_not_change_a_reachable_static_contract() -> None:
    chapter = chapter_length_contract(2_500, "fast", scene_count=2)
    assert chapter is not None

    recovered = recover_chapter_length_contract(
        chapter,
        accepted_characters=30_000,
        remaining_maximum_characters=20_000,
        book_minimum_characters=45_000,
    )

    assert recovered == chapter


def test_minimum_viable_length_floors_do_not_turn_soft_targets_into_hard_gates() -> None:
    chapter = chapter_length_contract(2_588, "fast", scene_count=2)
    assert chapter is not None

    assert minimum_viable_chapter_characters(chapter) == 1_294
    assert minimum_viable_book_characters(
        NarrativeScaleProfile(word_target_soft=7_500)
    ) == 5_250


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


def test_quantified_fact_repair_masks_only_one_bounded_sentence_window() -> None:
    chapter = _detail_chapter()
    chapter_contract = chapter_length_contract(2_500, "balanced", scene_count=2)
    assert chapter_contract is not None
    source_manifest = build_scene_manifest(
        _base_manifest(chapter),
        detail_chapter=chapter,
        scene_index=1,
        contract=next_scene_length_contract(
            chapter_contract,
            accepted_character_counts=[],
        ),
        output_tokens=2_100,
    )
    source = "她先核对晶片。她复核第三枚晶片，进度达到百分之六十七。随后关掉终端。"
    rejected = introduced_quantified_fact_tokens(source, source_manifest)

    window = quantified_fact_repair_window(source, rejected)
    repair_manifest = build_scene_fact_repair_manifest(
        source_manifest,
        window=window,
        output_tokens=420,
    )
    repaired = apply_quantified_fact_repair(
        source,
        window,
        "她重新核对晶片状态，确认异常仍在。",
    )

    assert window.left_context == "她先核对晶片。"
    assert window.right_context == "随后关掉终端。"
    assert window.masked_segment == (
        "她复核[未授权量化事实]晶片，进度达到[未授权量化事实]。"
    )
    serialized = repair_manifest.model_dump_json()
    assert "第三枚" not in serialized
    assert "百分之六十七" not in serialized
    assert "revision.source_draft" not in serialized
    assert repaired == "她先核对晶片。她重新核对晶片状态，确认异常仍在。随后关掉终端。"


def test_persistent_fact_gate_rejects_new_subject_relationship_and_career_history() -> None:
    manifest = _persistent_fact_manifest()

    findings = introduced_persistent_fact_violations(
        "周宁说她是林澈的姐姐。林澈随后承认自己曾任法医。",
        manifest,
    )

    assert {finding.code for finding in findings} == {
        "unregistered_scene_subject",
        "unfrozen_family_relation",
        "unfrozen_career_history",
    }


def test_persistent_fact_gate_rejects_new_access_document_and_custody() -> None:
    manifest = _persistent_fact_manifest()

    findings = introduced_persistent_fact_violations(
        "林澈从王强手中接过主控室钥匙，又拿出一份尸检报告。",
        manifest,
    )

    assert {finding.code for finding in findings} == {
        "unregistered_scene_subject",
        "unfrozen_access_or_key",
        "unfrozen_document_or_evidence",
        "unfrozen_evidence_custody",
    }


def test_persistent_fact_gate_does_not_treat_access_term_as_person() -> None:
    manifest = _persistent_fact_manifest()

    findings = introduced_persistent_fact_violations(
        "我看了下，权限是下午降的，说是例行清理。",
        manifest,
    )

    assert not any(
        finding.code == "unregistered_scene_subject" for finding in findings
    )


def test_persistent_fact_gate_still_rejects_person_holding_access() -> None:
    manifest = _persistent_fact_manifest()

    findings = introduced_persistent_fact_violations(
        "王强拿到权限。",
        manifest,
    )

    assert {finding.code for finding in findings} == {
        "unregistered_scene_subject",
        "unfrozen_access_or_key",
    }


def test_persistent_fact_gate_accepts_frozen_key_document_and_holder() -> None:
    manifest = _persistent_fact_manifest()

    findings = introduced_persistent_fact_violations(
        "林澈从顾言手中接过备用钥匙，调取了审计报告。",
        manifest,
    )

    assert findings == ()


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


def _persistent_fact_manifest() -> ContextManifest:
    chapter = _detail_chapter()
    base = _base_manifest(chapter).model_dump(mode="json")
    snippets = base["snippets"]
    cast = next(item for item in snippets if item["ref"] == "cast.subjects")
    cast.update(_context_snippet(
        "cast.subjects",
        "pov_scene_and_referenced_subjects",
        [
            {"id": "subject-1", "name": "林澈", "background": "公共档案修复师"},
            {"id": "subject-2", "name": "顾言", "background": "档案馆值班员"},
        ],
    ))
    detail = next(item for item in snippets if item["ref"] == "detail.chapter")
    detail.update(_context_snippet(
        "detail.chapter",
        "chapter_script",
        {
            **chapter.model_dump(mode="json"),
            "frozen_fact_examples": [
                "顾言把备用钥匙交给林澈保管。",
                "林澈使用备用钥匙调取审计报告。",
            ],
        },
    ))
    base["budget"]["input_chars"] = sum(len(item["text"]) for item in snippets)
    base["manifest_hash"] = _manifest_hash(base)
    return ContextManifest.model_validate(base)
