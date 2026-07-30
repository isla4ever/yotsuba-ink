from novel_workflow.orchestration.character_network import graph_from_brief
from novel_workflow.providers.base import PROMPT_SYSTEM_SPLIT, split_system_prompt
from novel_workflow.stages.prompt_plan import PromptPlanBuilder
from novel_workflow.workflows.run_schemas import ChapterContextPacket, NovelRunState
from novel_workflow.workflows.templates import default_workflow


def _state(**overrides) -> NovelRunState:
    state = NovelRunState(run_id="run-prompt", project_id="proj", workflow_id="default-novel-workflow")
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def _node(workflow, node_id):
    return next(node for node in workflow.nodes if node.id == node_id)


BRIEF_ARTIFACT = {
    "characters": [
        {"name": "林拾", "identity": "修复师", "motivation": "追查真相", "tier": "protagonist", "faction": "档案馆"},
        {"name": "沈决", "identity": "缉私警", "motivation": "洗刷冤屈", "tier": "major", "faction": "海关"},
        {"name": "周聿", "identity": "证人", "motivation": "隐瞒往事", "tier": "supporting"},
    ],
    "relationships": [
        {"source": "林拾", "target": "沈决", "relation": "调查同盟", "kind": "ally", "polarity": "complex", "strength": 0.7},
    ],
    "downstream_constraints": ["母亲失踪真相必须在终卷揭示"],
    "voice_spec": {
        "narration": "第三人称限制视角，过去时",
        "rhythm": "短句为主，对话叙述比 4:6",
        "banned_words": ["竟然", "不禁"],
        "per_character": [
            {"character": "林拾", "catchphrase": "先看档案再说", "speech_register": "克制专业"},
            {"character": "周聿", "catchphrase": "都过去了", "speech_register": "闪避含混"},
        ],
    },
}


def test_plan_splits_system_and_user_via_sentinel():
    workflow = default_workflow()
    state = _state()
    prompt = PromptPlanBuilder().build(_node(workflow, "info"), state)
    assert PROMPT_SYSTEM_SPLIT in prompt
    system, user = split_system_prompt(prompt)
    assert "## 角色任务" in system
    assert "## 硬约束" in system
    assert "## 输出结构" in system
    assert "## 阶段 Prompt 模板" in user
    assert "## 硬约束" not in user


def test_hard_constraints_carry_quota_world_rules_and_canon_conflicts():
    workflow = default_workflow()
    state = _state(
        artifacts={"info_recommend": BRIEF_ARTIFACT},
        canon_conflicts=[{"status": "pending", "target": "7A-13 母带", "claim_key": "condition"}],
    )
    state.story_bible.world_rules = ["磁带内容不得被无损复制"]
    plan = PromptPlanBuilder().build_plan(_node(workflow, "summary"), state)
    assert "磁带内容不得被无损复制" in plan.system
    assert "7A-13 母带" in plan.system
    assert "母亲失踪真相必须在终卷揭示" in plan.system
    assert "禁止新增任何人物" in plan.system


def test_l0_survives_even_under_tiny_budget():
    workflow = default_workflow()
    state = _state(artifacts={"info_recommend": BRIEF_ARTIFACT})
    state.story_bible.world_rules = ["磁带内容不得被无损复制"]
    plan = PromptPlanBuilder().build_plan(_node(workflow, "summary"), state, char_budget=400)
    assert "磁带内容不得被无损复制" in plan.system
    assert len(plan.user) <= 400 + 100
    assert "reference" in plan.dropped_layers


def test_crop_order_drops_reference_then_voice_then_entities():
    workflow = default_workflow()
    graph = graph_from_brief("info", BRIEF_ARTIFACT)
    state = _state(artifacts={"info_recommend": BRIEF_ARTIFACT}, character_graph=graph)
    full = PromptPlanBuilder().build_plan(_node(workflow, "summary"), state)
    assert full.dropped_layers == []
    assert "## 人物与阵营现状" in full.user
    assert "## 风格规格" in full.user

    reference_len = len("## 定稿 Story Brief / 参考依据")
    cropped = PromptPlanBuilder().build_plan(
        _node(workflow, "summary"),
        state,
        char_budget=len(full.user) - reference_len,
    )
    assert "reference" in cropped.dropped_layers
    assert "voice" not in cropped.dropped_layers or "entities" not in cropped.dropped_layers


def test_chapter_text_entities_filtered_to_current_chapter():
    workflow = default_workflow()
    graph = graph_from_brief("info", BRIEF_ARTIFACT)
    packet = ChapterContextPacket(
        chapter="第2章",
        chapter_index=2,
        chapter_outline="第2章｜POV：林拾｜场景：档案馆地下室；林拾与沈决核对磁带编号",
    )
    state = _state(artifacts={"info_recommend": BRIEF_ARTIFACT}, character_graph=graph, chapter_context_packets=[packet])
    plan = PromptPlanBuilder().build_plan(_node(workflow, "text"), state)
    assert "仅注入本章相关人物" in plan.user
    assert "林拾" in plan.user and "沈决" in plan.user
    entity_section = plan.user.split("## 人物与阵营现状")[1].split("##")[0]
    assert "周聿" not in entity_section


def test_voice_spec_injected_and_pov_sheet_prioritized():
    workflow = default_workflow()
    graph = graph_from_brief("info", BRIEF_ARTIFACT)
    packet = ChapterContextPacket(chapter="第2章", chapter_index=2, chapter_outline="POV：林拾 的调查")
    state = _state(artifacts={"info_recommend": BRIEF_ARTIFACT}, character_graph=graph, chapter_context_packets=[packet])
    plan = PromptPlanBuilder().build_plan(_node(workflow, "text"), state)
    assert "## 风格规格" in plan.user
    assert "先看档案再说" in plan.user
    voice_section = plan.user.split("## 风格规格")[1]
    assert "都过去了" not in voice_section


def test_openai_adapter_split_contract_roundtrip():
    system, user = split_system_prompt(f"SYS{PROMPT_SYSTEM_SPLIT}USER")
    assert (system, user) == ("SYS", "USER")
    assert split_system_prompt("plain prompt") == ("", "plain prompt")
