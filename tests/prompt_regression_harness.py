from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from novel_workflow.orchestration.character_network import graph_from_brief
from novel_workflow.stages.prompt_plan import PromptPlanBuilder
from novel_workflow.workflows.run_schemas import ChapterContextPacket, NovelRunState
from novel_workflow.workflows.templates import default_workflow

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_STAGE_IDS = ("info", "summary", "outline", "detail", "text", "cover")

BRIEF = {
    "selected_title": "雾港旧声",
    "synopsis": "声纹修复师林拾从旧磁带中听见尚未发生的求救，并在三天内追查被篡改的港区记忆档案。",
    "worldbuilding_detail": "雾港以声音档案确认公共事实；潮汐钟每晚零点封存当天记录，母带不可被无损复制。",
    "characters": [
        {"name": "林拾", "identity": "声纹修复师", "motivation": "查明母亲失踪真相", "tier": "protagonist", "faction": "档案馆"},
        {"name": "沈决", "identity": "缉私警", "motivation": "洗刷旧案冤屈", "tier": "major", "faction": "海关"},
        {"name": "周聿", "identity": "旧案证人", "motivation": "隐瞒实验往事", "tier": "supporting", "faction": "港务会"},
    ],
    "relationships": [
        {"source": "林拾", "target": "沈决", "relation": "调查同盟", "kind": "ally", "polarity": "complex", "strength": 0.7},
        {"source": "林拾", "target": "周聿", "relation": "追问与隐瞒", "kind": "rival", "polarity": "negative", "strength": 0.8},
    ],
    "downstream_constraints": ["母亲失踪真相必须在终卷揭示", "7A-13 母带不能被无损复制"],
    "voice_spec": {
        "narration": "第三人称限制视角，过去时",
        "rhythm": "短句为主，对话叙述比 4:6",
        "banned_words": ["竟然", "不禁"],
        "cliche_slots": ["靠巧合发现全部真相"],
        "per_character": [
            {"character": "林拾", "catchphrase": "先看档案再说", "speech_register": "克制专业"},
            {"character": "周聿", "catchphrase": "都过去了", "speech_register": "闪避含混"},
        ],
    },
}


def regression_state() -> NovelRunState:
    state = NovelRunState(
        run_id="prompt-regression-v1",
        project_id="prompt-regression-project",
        workflow_id="default-novel-workflow",
        inputs={
            "title": "雾港旧声",
            "theme": "悬疑、记忆、旧港、群像",
            "stage_configs": {
                "info": {"genre": "悬疑", "audience": "成年悬疑读者", "reference_mode": "smart_search", "reference_summary": "仅参考声音取证与港口档案制度，不复用具体桥段。"},
                "summary": {"target_words": 30000, "structure": "三幕式"},
                "outline": {"volume_count": 2, "chapters_per_volume": 6},
                "detail": {"chapter_count": 12, "must_include": "7A-13 母带与潮汐钟"},
                "text": {"chapter_words": 1800, "pov": "林拾"},
                "cover": {"cover_style": "克制的档案悬疑", "aspect_ratio": "2:3"},
            },
        },
        artifacts={
            "info_recommend": BRIEF,
            "summary": {"full_synopsis": "林拾循着未来求救声追查旧案，并发现港务会用潮汐钟改写公共记忆。"},
            "outline": {"volumes": [{"title": "潮声证词", "chapter_range": "1-6", "volume_goal": "确认磁带来自未来"}]},
            "detail_outline": {"chapters": [{"chapter": "第2章", "pov": "林拾", "scene": "档案馆地下室", "goal": "核对母带编号"}]},
        },
        story_brief={"content": "《雾港旧声》已确认 Story Brief：声音档案决定公共事实，林拾负责追查 7A-13 母带。"},
        character_graph=graph_from_brief("info", BRIEF),
        chapter_context_packets=[ChapterContextPacket(
            chapter="第2章",
            chapter_index=2,
            chapter_outline="POV：林拾；林拾与沈决在档案馆地下室核对 7A-13 母带",
            previous_chapter_summary="林拾第一次听见未来求救。",
            volume_goal="确认磁带来自未来",
            volume_title="潮声证词",
            volume_chapter_range="第1-6章",
            next_volume_goal="追查潮汐钟改写记录的机制",
            transition_directive="转场类型：连续因果下的场景转换。默认沿上一章结果向下续写，用因果或人物反应抵达本章进入状态，禁止重新介绍故事。",
            open_foreshadows=[{"name": "潮汐钟缺失的一分钟"}],
            world_rules=["母带不可被无损复制"],
        )],
        canon_conflicts=[{"status": "pending", "target": "7A-13 母带", "claim_key": "recorded_at"}],
    )
    state.story_bible.world_rules = ["母带不可被无损复制", "潮汐钟零点封存当天记录"]
    return state


def prompt_template(template_id: str) -> str:
    path = REPO_ROOT / "runtime" / "novel_workflow" / "prompts" / f"{template_id}.json"
    return str(json.loads(path.read_text(encoding="utf-8"))["content"])


def build_stage_plan(stage_id: str, *, template_suffix: str = ""):
    workflow = default_workflow()
    node = next(item for item in workflow.nodes if item.id == stage_id)
    template = prompt_template(node.prompt_template_id)
    if template_suffix:
        template = f"{template}\n\n{template_suffix}"
    return PromptPlanBuilder().build_plan(node, regression_state(), template_content=template)


def plan_snapshot(plan) -> dict[str, Any]:
    rendered = plan.render()
    return {
        "system_sha256": _sha256(plan.system),
        "user_sha256": _sha256(plan.user),
        "render_sha256": _sha256(rendered),
        "system_chars": len(plan.system),
        "user_chars": len(plan.user),
        "dropped_layers": plan.dropped_layers,
        "system_headings": _headings(plan.system),
        "user_headings": _headings(plan.user),
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _headings(value: str) -> list[str]:
    return [line for line in value.splitlines() if line.startswith("## ")]
