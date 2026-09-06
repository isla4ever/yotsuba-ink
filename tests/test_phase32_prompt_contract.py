from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.phase32_route_artifacts import (
    ScreenplayBriefArtifact,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.phase32_prompt_contract import (
    PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER,
    build_phase32_provider_task_snapshot,
)
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import (
    SCREENPLAY_SAMPLE_ROUTE,
    official_creation_routes,
)


WAVE18_DEFINITION_DIGEST = (
    "24de5756055fa3b010075095c7f3ca069bcbd7bda4c55ea22121821007e36939"
)
WAVE18_BRIEF_PROMPT_DIGEST = (
    "b14fa602b6d72fe70f5736ab2617ae3fb546bea52ac0ac7066595d651d9fe457"
)
WAVE18_BRIEF_SCHEMA_DIGEST = (
    "e8bf68f9f9f9229681803c2de061f5abcc14b2eed7f571ee42d8afbf8f2eee0a"
)
BRIEF_V2_PROMPT_DIGEST = (
    "8b508fcaec1dc70c1cf5b837f765a1344d900e28fc6a321fa47fe85b7bb10aba"
)
BRIEF_V3_PROMPT_DIGEST = (
    "d7fecfc4440121deff3c2ceee0739b9603dff3d9c0cd20e57fec4da43a1da18f"
)
BRIEF_V4_PROMPT_DIGEST = (
    "092f4fe2e5dd28542801845b33b196b4bb1c073679e321d548be69c1c4da357a"
)
BRIEF_V2_SCHEMA_DIGEST = (
    "a0c38f7ffd0a7c9ac2d6d43abdd6f133fc965484a545773a8d4ab28a2ab7e15f"
)
BRIEF_V4_SCHEMA_DIGEST = (
    "79b5f531f94df90cbdb374335a84b2509ed3f547bce99d362e97846a95d68e31"
)
CAST_V2_PROMPT_DIGEST = (
    "91016a2c652f1837e33ae20575f958e3e01fc1227ab554a9f80faa94b54180ee"
)
CAST_V5_PROMPT_DIGEST = (
    "3a923de0b7d92ae267bd208fd7bbcd9c557f618a4ce7d10f409fef024c458e3c"
)
CAST_V2_SCHEMA_DIGEST = (
    "4273663d5e3754a5cfc628a4ffabd36cda4bf57ec45e993635fad6fd69980ba2"
)

EXPECTED_TASK_PROMPT_REVISIONS = {
    "screenplay_brief": 4,
    "novel_brief": 3,
    "character_bible": 5,
    "beat_board": 4,
    "scene_deck": 4,
    "screenplay_draft": 4,
    "story_map": 4,
    "section_plan": 4,
    "short_prose_unit": 4,
    "book_architecture": 3,
    "volume_architecture": 2,
    "rolling_detail": 6,
    "chapter": 6,
    "cover": 3,
}


def _screenplay_task_snapshot(stage_index: int):
    manifest = RouteGraphCompiler().compile(SCREENPLAY_SAMPLE_ROUTE)
    return build_phase32_provider_task_snapshot(
        "screenplay_sample",
        manifest.stages[stage_index],
    )


def test_all_official_provider_stages_freeze_explicit_language_contract() -> None:
    task_kinds: set[str] = set()
    for route in official_creation_routes():
        manifest = RouteGraphCompiler().compile(route)
        for stage in manifest.stages:
            if stage.provider_task_kind is None:
                continue
            snapshot = build_phase32_provider_task_snapshot(route.route_id, stage)
            task_kinds.add(snapshot.provider_task_kind)
            revision = EXPECTED_TASK_PROMPT_REVISIONS[snapshot.provider_task_kind]
            assert snapshot.prompt_template_id == (
                f"prompt.phase32.{route.route_id}.{stage.stage_id}.v{revision}"
            )
            assert PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER in snapshot.prompt_template
            assert "当前产品只接受 zh-CN" in snapshot.prompt_template
            assert "自然语言字段必须使用简体中文" in snapshot.prompt_template
            assert "稳定 ref 与 code-owned metadata" in snapshot.prompt_template

    assert task_kinds == set(EXPECTED_TASK_PROMPT_REVISIONS)
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/workflows/phase32_prompt_contract.py"
    ).read_text(encoding="utf-8")
    assert "_TASK_PROMPT_REVISIONS.get" not in source


def test_screenplay_brief_v4_freezes_title_semantics_and_language_authority() -> None:
    snapshot = _screenplay_task_snapshot(0)
    properties = snapshot.output_schema["properties"]

    assert snapshot.prompt_template_id == "prompt.phase32.screenplay_sample.brief.v4"
    assert "正式中文片名 title" in snapshot.prompt_template
    assert "禁止复制 screenplay_sample" in snapshot.prompt_template
    assert "具体对抗者或阻力" in snapshot.prompt_template
    assert "失去什么、换来什么" in snapshot.prompt_template
    assert "不得填写 screenplay_sample" in properties["sample_type"]["description"]
    assert "本故事独有" in properties["audience_promise"]["description"]
    assert "不可逆选择" in properties["visible_conflict"]["description"]
    assert "留下哪个可继续追查的问题" in properties["ending_effect"]["description"]
    assert snapshot.prompt_template_digest == BRIEF_V4_PROMPT_DIGEST
    assert snapshot.prompt_template_digest != BRIEF_V3_PROMPT_DIGEST
    assert snapshot.prompt_template_digest != BRIEF_V2_PROMPT_DIGEST
    assert snapshot.output_schema_digest == BRIEF_V4_SCHEMA_DIGEST
    assert snapshot.output_schema_digest != BRIEF_V2_SCHEMA_DIGEST


def test_beat_board_v4_preserves_decision_and_stable_ascii_ref_contracts() -> None:
    snapshot = _screenplay_task_snapshot(2)
    beat_schema = snapshot.output_schema["$defs"]["BeatBoardBeat"]["properties"]
    ref_schema = beat_schema["setup_or_payoff_refs"]

    assert snapshot.prompt_template_id == "prompt.phase32.screenplay_sample.beat_board.v4"
    assert "自然语言内容必须使用简体中文" in snapshot.prompt_template
    assert "不得输出英文剧情说明" in snapshot.prompt_template
    assert "‘No decision’或同义占位" in snapshot.prompt_template
    assert "setup_abnormal_signal" in snapshot.prompt_template
    assert "禁止填写 setup: 异常信号" in snapshot.prompt_template
    assert "简体中文" in beat_schema["dramatic_job"]["description"]
    assert "简体中文" in beat_schema["visible_pressure"]["description"]
    assert "简体中文" in beat_schema["character_decision"]["description"]
    assert "No decision" in beat_schema["character_decision"]["description"]
    assert "简体中文" in beat_schema["outcome"]["description"]
    assert "Stable ASCII setup/payoff identifiers" in ref_schema["description"]
    assert "Do not use labels with colons" in ref_schema["description"]


def test_character_bible_v5_preserves_claim_custody_and_registers_distinct_subjects() -> None:
    snapshot = _screenplay_task_snapshot(1)
    character = snapshot.output_schema["$defs"]["CharacterRecord"]["properties"]
    relation = snapshot.output_schema["$defs"]["CharacterRelationship"]["properties"]

    assert snapshot.prompt_template_id == "prompt.phase32.screenplay_sample.cast.v5"
    assert "epistemic_custody" in snapshot.prompt_template
    assert "不是 Canon" in snapshot.prompt_template
    assert "开放问题、怀疑、未来结果和风险不得写成人物事实" in snapshot.prompt_template
    assert "必须登记为一个 character" in snapshot.prompt_template
    assert "必须在 Cast 阶段拆成不同 subject_ref" in snapshot.prompt_template
    assert "作者工作名" in snapshot.prompt_template
    assert "不得把多个独立主体合并成一个集合角色" in snapshot.prompt_template
    assert "不得借命名补写未证实的身份揭示" in snapshot.prompt_template
    assert "hidden guilt" in character["role"]["description"]
    assert "distinguish risks" in character["stakes"]["description"]
    assert "suspected culpability" in relation["pressure"]["description"]
    assert snapshot.prompt_template_digest == CAST_V5_PROMPT_DIGEST
    assert snapshot.prompt_template_digest != CAST_V2_PROMPT_DIGEST
    assert snapshot.output_schema_digest == CAST_V2_SCHEMA_DIGEST


def test_book_architecture_v3_distinguishes_new_refs_from_upstream_artifact_refs() -> None:
    manifest = RouteGraphCompiler().compile(next(
        route for route in official_creation_routes() if route.route_id == "long_novel"
    ))
    stage = next(item for item in manifest.stages if item.stage_id == "book_architecture")
    snapshot = build_phase32_provider_task_snapshot("long_novel", stage)
    assert snapshot.prompt_template_id == "prompt.phase32.long_novel.book_architecture.v3"
    assert "当前 Artifact 新建的稳定 ASCII 引用" in snapshot.prompt_template
    assert "不得把上游 Artifact ref" in snapshot.prompt_template
    assert "promise_archive" in snapshot.prompt_template


def test_short_novel_v4_freezes_promise_coverage_and_character_names() -> None:
    manifest = RouteGraphCompiler().compile(next(
        route for route in official_creation_routes() if route.route_id == "short_novel"
    ))
    snapshots = {
        stage.stage_id: build_phase32_provider_task_snapshot("short_novel", stage)
        for stage in manifest.stages
        if stage.stage_id in {"story_map", "section_plan", "text"}
    }

    assert snapshots["story_map"].prompt_template_id == (
        "prompt.phase32.short_novel.story_map.v4"
    )
    assert "每个 anchor 至少填写一个 promise_ref" in snapshots["story_map"].prompt_template
    assert "禁止用空数组绕过承诺追踪" in snapshots["story_map"].prompt_template
    assert "每个 anchor 都必须显式带上" in snapshots["story_map"].prompt_template
    assert snapshots["section_plan"].prompt_template_id == (
        "prompt.phase32.short_novel.section_plan.v4"
    )
    assert "所有 Story Map promise_ref 必须至少被一个 unit 承接" in (
        snapshots["section_plan"].prompt_template
    )
    assert "每个 unit 都必须显式带上 promise_refs" in snapshots["section_plan"].prompt_template
    assert snapshots["text"].prompt_template_id == (
        "prompt.phase32.short_novel.text.v4"
    )
    assert "display_name 是人物唯一有效称谓" in snapshots["text"].prompt_template
    assert "不得给已登记人物另造姓名" in snapshots["text"].prompt_template
    assert "不得给未登记的行动者" in snapshots["text"].prompt_template


def test_rolling_detail_v6_freezes_nested_fields_local_cast_and_exact_12_compaction() -> None:
    manifest = RouteGraphCompiler().compile(next(
        route for route in official_creation_routes() if route.route_id == "long_novel"
    ))
    stage = next(item for item in manifest.stages if item.stage_id == "rolling_detail")
    snapshot = build_phase32_provider_task_snapshot("long_novel", stage)
    assert snapshot.prompt_template_id == "prompt.phase32.long_novel.rolling_detail.v6"
    assert "volume_ref、title、pov_subject_ref、cast_subject_refs" in snapshot.prompt_template
    assert "禁止使用 summary、characters、time 等旧别名" in snapshot.prompt_template
    assert "window_main、chapter_01、scene_01_01" in snapshot.prompt_template
    assert "只引用 Volumes 中 ordinal 最小的第一卷" in snapshot.prompt_template
    assert "总计恰好十二章" in snapshot.prompt_template
    assert "优先保证 JSON 完整闭合" in snapshot.prompt_template
    assert "handoff 若要承接下一章尚未进入本章范围的人物" in snapshot.prompt_template
    assert "章节允许的角色不自动等于每个场景允许的角色" in snapshot.prompt_template
    assert "不得仅为容纳越界姓名" in snapshot.prompt_template


def test_long_chapter_v6_freezes_continuity_and_registered_character_names() -> None:
    manifest = RouteGraphCompiler().compile(next(
        route for route in official_creation_routes() if route.route_id == "long_novel"
    ))
    stage = next(item for item in manifest.stages if item.stage_id == "text")
    snapshot = build_phase32_provider_task_snapshot("long_novel", stage)

    assert snapshot.prompt_template_id == "prompt.phase32.long_novel.text.v6"
    assert "display_name 是人物唯一有效称谓" in snapshot.prompt_template
    assert "只允许使用当前 chapter.cast_subject_refs" in snapshot.prompt_template
    assert "不得给未登记的行动者" in snapshot.prompt_template
    assert "任何身份揭示都必须先通过已接受 Cast 修订" in snapshot.prompt_template
    assert "不要输出‘注：’、括号说明" in snapshot.prompt_template
    assert "不得出现任何不在冻结 Cast display_name列表中的中文人名" in snapshot.prompt_template
    assert "正确写法是‘我必须找到失踪者’，错误写法是‘我必须找到苏晚’" in snapshot.prompt_template
    assert "previous_chapter_tail 只是不可变更的连续性参考" in snapshot.prompt_template
    assert "不得复制、改写、摘要或重演" in snapshot.prompt_template
    assert "已建立的日期、时间和事件顺序不得重置" in snapshot.prompt_template
    assert "证据、工具和测量精度必须符合可观测条件" in snapshot.prompt_template
    assert "不少于其百分之六十" in snapshot.prompt_template


def test_wave24_live_brief_fixture_preserves_the_language_failure_evidence() -> None:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures/phase32_wave24_brief_language_drift.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["provider_calls"] == 1
    assert fixture["frozen_inputs"].get("creation_language") is None
    assert fixture["prompt_template_id"] == "prompt.phase32.screenplay_sample.brief.v2"
    assert fixture["observation"] == (
        "all_author_facing_natural_language_returned_in_english"
    )
    assert fixture["artifact_payload"]["sample_type"] == (
        "single-location real-time thriller excerpt"
    )
    assert fixture["run_state"] == {
        "status": "awaiting_decision",
        "stage_id": "brief",
        "domain_revision": 0,
    }


def test_wave18_run_remains_readable_but_old_brief_is_not_current_input() -> None:
    root = Path(__file__).resolve().parents[1]
    definition_path = (
        root
        / "runtime/novel_workflow/phase32_runtime/runs"
        / "p32-screenplay-brief-live-20260823-020459/definition.json"
    )
    if definition_path.exists():
        definition = GraphRunDefinition.model_validate(
            json.loads(definition_path.read_text(encoding="utf-8"))
        )
        brief = definition.provider_bindings_by_stage[0].binding.payload["task"]
        assert definition.definition_digest == WAVE18_DEFINITION_DIGEST
        assert brief["prompt_template_digest"] == WAVE18_BRIEF_PROMPT_DIGEST
        assert brief["output_schema_digest"] == WAVE18_BRIEF_SCHEMA_DIGEST

    historical_payload = {
        "sample_type": "screenplay_sample",
        "target_minutes": 12,
        "premise": "旧候选仍需只读。",
        "audience_promise": "旧候选仍需只读。",
        "visible_conflict": "旧候选仍需只读。",
        "ending_effect": "旧候选仍需只读。",
        "tone": "克制",
    }
    with pytest.raises(ValidationError, match="title"):
        ScreenplayBriefArtifact.model_validate(historical_payload)
