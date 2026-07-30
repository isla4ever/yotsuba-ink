from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.providers.base import TextProvider
from tests.fakes import FakeImageProvider, FakeTextProvider, fake_model_review_output
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import WorkflowDefinition
from novel_workflow.workflows.templates import default_workflow


class CapturingInfoProvider(TextProvider):
    name = "capturing-info"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise AssertionError("single-stage runner should request structured output")

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        self.calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
        return story_brief_fixture(str(context.get("title") or "雾港单阶段"))


class CapturingPlanningProvider(TextProvider):
    name = "capturing-planning"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise AssertionError("runner should request structured output")

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        self.calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
        if task_name == "info_recommend":
            return story_brief_fixture(str(context.get("title") or "雾港规划"))
        if task_name == "summary":
            return summary_fixture()
        if task_name == "outline":
            return outline_fixture()
        if task_name == "detail_outline":
            return detail_outline_fixture()
        if task_name == "chapter_text":
            return chapter_text_fixture()
        if task_name == "model_review":
            return fake_model_review_output()
        raise AssertionError(f"unexpected task: {task_name}")


def planning_workflow(node_ids: list[str], *, provider_profile_id: str) -> WorkflowDefinition:
    workflow = default_workflow().model_copy(deep=True)
    original_nodes = {node.id: node for node in workflow.nodes}
    workflow.nodes = []
    for node_id in node_ids:
        node = deepcopy(original_nodes[node_id])
        node.provider_profile_id = provider_profile_id
        node.variant_policy.enabled = False
        workflow.nodes.append(node)
    allowed = set(node_ids)
    workflow.edges = [edge for edge in workflow.edges if edge.source in allowed and edge.target in allowed]
    workflow.stage_configs = {node_id: workflow.stage_configs[node_id] for node_id in node_ids}
    for node in workflow.nodes:
        workflow.stage_configs[node.id].provider_profile_id = provider_profile_id
        workflow.stage_configs[node.id].model_settings = node.model_settings
        workflow.stage_configs[node.id].variant_policy = node.variant_policy
    workflow.quality_mode = "balanced"
    return workflow


def provider_registry(provider: TextProvider) -> ProviderRegistry:
    return ProviderRegistry(
        text_provider=FakeTextProvider(),
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": FakeTextProvider(), "openai-compatible": provider},
        image_providers={"openai-compatible-image": FakeImageProvider()},
    )


async def run_and_approve(
    runner: NovelWorkflowRunner,
    workflow: WorkflowDefinition,
    store: RunStore,
    run_id: str,
    inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    async def approve_when_needed() -> None:
        confirmed: set[str] = set()
        for _ in range(180):
            await asyncio.sleep(0.05)
            approval = store.read(run_id).get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id not in confirmed:
                store.approve_artifact(
                    run_id,
                    node_id=node_id,
                    output_key=str(approval["output_key"]),
                    artifact=approval["artifact"],
                )
                confirmed.add(node_id)
            state = store.read(run_id).get("state") or {}
            if state.get("runtime_phase") in {"completed", "failed"}:
                return

    approver = asyncio.create_task(approve_when_needed())
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        await approver
    return events


def build_runner(tmp_path: Any, provider: TextProvider) -> tuple[RunStore, NovelWorkflowRunner]:
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    runner = NovelWorkflowRunner(providers=provider_registry(provider), wiki_store=wiki, run_store=store)
    return store, runner


def story_brief_fixture(title: str) -> dict[str, Any]:
    return {
        "selected_title": title,
        "title_candidates": [title, "旧声回潮", "蓝潮证词", "雾钟未眠", "7A-13 回声"],
        "synopsis": "旧港声纹修复师在一盘旧磁带中听见十年前的求救声，追查后发现证词被蓝潮实验改写。",
        "worldbuilding_detail": "旧港的雾钟系统记录声纹证词，蓝潮实验曾用它筛选并改写关键证词，档案馆、港务集团和实验区构成核心场域。",
        "characters": [
            {"name": "林澈", "identity": "声纹档案修复师", "motivation": "查清父亲与蓝潮实验的关系", "relations": "与许望舒合作追查", "growth_direction": "从回避旧案到公开档案"},
            {"name": "许望舒", "identity": "调查记者", "motivation": "证明旧港失踪案真实存在", "relations": "推动林澈面对证据", "growth_direction": "从追报道到保护证人"},
            {"name": "周泊言", "identity": "旧案幸存者", "motivation": "确认自己被篡改的证词", "relations": "既是向导也是风险源", "growth_direction": "从隐瞒经历到交出证据"},
        ],
        "relationships": [
            {"source": "林澈", "target": "许望舒", "relation": "调查同盟", "strength": 0.7},
            {"source": "林澈", "target": "周泊言", "relation": "互相试探", "strength": 0.55},
        ],
        "tags": ["悬疑", "旧港", "记忆实验"],
        "downstream_constraints": ["雾钟是技术装置，不是超自然解释", "人物关系变化必须由证据推进"],
        "risk_notes": ["避免万能记忆篡改"],
    }


def summary_fixture() -> dict[str, Any]:
    return {
        "one_liner": "一盘旧磁带让三名旧案相关者发现，旧港失踪案背后隐藏着以声纹改写证词的蓝潮实验。",
        "full_synopsis": "林澈在修复 7A-13 磁带时听见来自十年前的求救声，声音指向旧港档案馆被删除的失踪案。许望舒带来未公开采访材料，周泊言承认自己是蓝潮实验幸存者，却不愿解释证词为何前后矛盾。三人沿着雾钟码头、蓝潮实验区和港务旧楼追查，确认雾钟记录的是被人为筛选过的证词回声。结尾处，他们公开第一批声纹档案，迫使港务集团承认旧案存在，同时留下林澈父亲签章和备用电源两条更深长线，作为后续章节继续推进的伏笔。",
        "act_structure": [
            {"title": "磁带入局", "goal": "建立 7A-13 母带与旧港失踪案关联", "turn": "求救声说出林澈只在私人记忆里听过的称呼"},
            {"title": "蓝潮追查", "goal": "确认声纹档案与幸存者证词被技术性篡改", "turn": "周泊言交出缺页名单却隐瞒自己的证词版本"},
            {"title": "雾钟公开", "goal": "公开第一批证据并保留更深追查动机", "turn": "父亲签章进入主线，雾钟在无人操作时再次响起"},
        ],
        "core_conflict": "个人记忆与公共档案互相冲突，真相公开会威胁仍在运作的港务利益链，也会迫使林澈重新判断父亲是否参与蓝潮实验。",
        "character_arcs": [
            {"name": "林澈", "arc": "从修复档案的人变成公开档案的人", "pressure": "父亲可能参与蓝潮实验", "next": "判断亲情和证据之间的边界"},
            {"name": "许望舒", "arc": "从追逐报道转向保护证人", "pressure": "采访材料可能让周泊言暴露", "next": "建立证人保护与公开节奏"},
            {"name": "周泊言", "arc": "从隐瞒幸存者身份到交出缺页名单", "pressure": "证词被改写导致他无法完全自证", "next": "用行动恢复同盟信任"},
        ],
        "key_turns": [
            {"label": "7A-13 母带", "detail": "求救声与林澈私人记忆重叠，让旧案从公共事件变成私人危机。"},
            {"label": "缺页名单", "detail": "许望舒发现删改日志与幸存者名单不一致，推动三人结盟。"},
            {"label": "雾钟提前响起", "detail": "系统在无人操作时播放新的证词回声，证明蓝潮链路仍未终止。"},
        ],
        "ending_resolution": "投稿项以第一层真相公开收束，同时保留父亲签章、备用电源和周泊言原始证词三条后续长线。",
        "consistency_checks": ["雾钟仍是技术装置", "人物关系变化由证据推进", "伏笔均有投放或延后标记"],
    }


def outline_fixture() -> dict[str, Any]:
    return {
        "volumes": [
            {
                "title": "第一卷：7A-13 母带",
                "chapter_range": "第1-3章",
                "volume_goal": "完成旧案入口、三人结盟和第一层真相揭示。",
                "rhythm": "悬念递进，第三章爆点",
                "opening": "林澈修复磁带，听见十年前求救声。",
                "development": "许望舒带来删改日志，周泊言暴露幸存者身份。",
                "midpoint": "蓝潮实验区证据证明证词被筛选。",
                "climax": "雾钟在无人操作下提前响起。",
                "resolution": "三人公开第一批声纹档案，并留下父亲签章。",
                "character_progression": [{"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "公开证据可能暴露证人", "change": "从回避旧案到主动追查父亲签章", "impact": "下一卷继续校准证据与信任边界"}],
                "world_reveal": [{"anchor": "雾钟", "reveal": "它是声纹证词记录装置，不是传说", "rule": "只能记录和筛选既有声纹", "impact": "后续细纲必须保留技术证据链"}],
                "foreshadow_plan": [{"name": "父亲签章", "status": "投放", "chapter_range": "第3章", "note": "卷尾露出但不解释"}],
            }
        ]
    }


def detail_outline_fixture() -> dict[str, Any]:
    return {
        "chapters": [
            {
                "chapter": "第1章",
                "pov": "林澈",
                "scene": "旧港档案馆",
                "goal": "修复 7A-13 母带并确认求救声来源",
                "entry_state": "林澈只想完成普通修复委托",
                "conflict": "磁带底噪出现他的名字，档案馆主管要求停止修复",
                "stakes": "如果母带被封存，旧案入口和个人记忆线索都会消失",
                "fact_reveals": [{"anchor": "雾钟", "fact": "7A-13 母带真实存在", "impact": "旧案获得可验证入口"}],
                "foreshadow": [{"name": "父亲签章", "status": "投放", "note": "求救声暗示签章与旧案相连"}],
                "character_shift": {"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "证据可能被封存", "motivation": "保住母带物证", "change": "从回避旧案转向主动保留证据", "impact": "下一章继续追查母带来源"},
                "hook": "求救声来自十年前，却喊出林澈现在使用的名字",
                "continuity_notes": "承接 info 中声纹档案设定，并投放父亲签章长线",
                "wiki_candidates": [{"title": "7A-13 母带", "fact": "保存十年前声纹证词", "source_anchor": "雾钟"}],
            },
            {
                "chapter": "第2章",
                "pov": "许望舒",
                "scene": "雾钟码头",
                "goal": "追查母带来源并找到删改日志",
                "entry_state": "许望舒掌握未公开采访材料但缺少物证",
                "conflict": "周泊言拒绝承认幸存者身份，码头黑市开始清理磁带",
                "stakes": "证人再次消失会让调查同盟失去可信来源",
                "fact_reveals": [{"anchor": "蓝潮", "fact": "名单缺页且黑市磁带与母带同批", "impact": "证据链指向实验项目"}],
                "foreshadow": [{"name": "匿名删改签名", "status": "投放", "note": "签名将在卷尾指向林澈父亲"}],
                "character_shift": {"character": "许望舒", "related_to": "林澈", "relation": "调查同盟", "pressure": "证人可能再次消失", "motivation": "保护证人与物证", "change": "从追逐报道转向保护证人", "impact": "调查同盟的公开节奏改变"},
                "hook": "删改日志出现林澈父亲缩写",
                "continuity_notes": "推进调查同盟，并承接第1章母带异常",
                "wiki_candidates": [{"title": "蓝潮名单", "fact": "存在人为移除的缺页", "source_anchor": "蓝潮"}],
            },
            {
                "chapter": "第3章",
                "pov": "林澈",
                "scene": "蓝潮实验区",
                "goal": "确认雾钟机制并公开第一批声纹档案",
                "entry_state": "三人暂时结盟但互相保留秘密",
                "conflict": "现实记录与幸存者记忆冲突，公开证据会暴露三人位置",
                "stakes": "如果公开失败，港务集团会彻底销毁母带链路",
                "fact_reveals": [{"anchor": "雾钟", "fact": "备用电源仍可运行，证词只会被筛选", "impact": "排除超自然与凭空伪造解释"}],
                "foreshadow": [{"name": "父亲签章", "status": "推进", "note": "卷尾露出但不解释签章来源"}],
                "character_shift": {"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "公开证据会暴露三人", "motivation": "让旧案进入公共记录", "change": "决定公开第一批档案", "impact": "后续必须承担公开后的追捕压力"},
                "hook": "雾钟无人操作却提前响起新的证词回声",
                "continuity_notes": "完成第一层真相揭示，并把父亲签章留给后续正文",
                "wiki_candidates": [{"title": "雾钟备用电源", "fact": "在无人操作时仍保持运行", "source_anchor": "雾钟"}],
            },
        ]
    }


def chapter_text_fixture() -> dict[str, Any]:
    return {
        "chapter_title": "第1章 7A-13 母带",
        "content": (
            "林澈把 7A-13 母带推进修复机时，旧港档案馆的灯正好暗了一下。"
            "磁粉在玻璃窗后缓慢旋转，底噪像潮水贴着耳膜涌来，他原本只想完成一次普通修复，"
            "却在第三遍降噪后听见有人叫出他的名字。声音很轻，像隔着十年的雾钟传来，"
            "又准确地落在他现在使用的工作编号上。\n\n"
            "主管推门进来，要求他立刻停止拷贝，理由是这盘磁带属于港务旧案封存件。"
            "林澈没有争辩，只把备用通道切到离线，把那一句求救声截成三段。"
            "第一段是码头风声，第二段是女人压低的呼吸，第三段里出现了父亲签章对应的旧式校验音。"
            "这个细节不可能来自传说，雾钟从来不是神秘仪式，它是旧港用来记录声纹证词的技术装置。\n\n"
            "许望舒发来的消息在屏幕边缘亮起：别交母带，删改日志今晚会被清理。"
            "林澈望着修复波形里突然升高的蓝色脉冲，第一次没有把旧案推回档案柜深处。"
            "他复制了证据，也复制了自己的犹豫。门外脚步声逼近时，磁带里的求救声再次响起，"
            "这一次，它说出了一个尚未发生的地点：雾钟码头。"
        ),
        "summary": "林澈修复 7A-13 母带时听见十年前求救声，并发现父亲签章与雾钟声纹证词装置有关，决定保留证据。",
        "wiki_writebacks": [
            {"target": "7A-13 母带", "fact": "包含十年前求救声与父亲签章校验音", "source_chapter": "第1章"},
            {"target": "雾钟系统", "fact": "是旧港记录声纹证词的技术装置", "source_chapter": "第1章"},
        ],
        "character_shift": "林澈从完成普通委托转向主动保留旧案证据。",
        "foreshadow_updates": [
            {"name": "父亲签章", "status": "投放"},
            {"name": "雾钟码头", "status": "投放"},
        ],
    }
