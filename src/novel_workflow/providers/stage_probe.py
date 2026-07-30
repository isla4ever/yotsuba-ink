from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from novel_workflow.output_contracts import validate_chapter_generation, validate_stage_artifact
from novel_workflow.providers.errors import ProviderResponseError, public_provider_failure
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.stages.prompt_plan import PromptPlanBuilder
from novel_workflow.workflows.schemas import ChapterContextPacket, NovelRunState, ProviderProfile
from novel_workflow.workflows.templates import default_workflow


class StageProbeResult(BaseModel):
    ok: bool
    provider_id: str
    stage_id: str
    stage_type: str
    schema_name: str = ""
    message: str = ""
    error_code: str = ""
    errors: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


async def probe_structured_stage(
    provider_profile: ProviderProfile,
    *,
    api_key: str,
    stage_id: str = "info",
    inputs: dict[str, Any] | None = None,
    max_tokens: int | None = None,
) -> StageProbeResult:
    workflow = default_workflow()
    node = next((item for item in workflow.nodes if item.id == stage_id), None)
    if node is None:
        return StageProbeResult(ok=False, provider_id=provider_profile.id, stage_id=stage_id, stage_type="", error_code="unknown_stage", message=f"Unknown stage: {stage_id}")
    provider = OpenAICompatibleTextProvider.from_profile(
        base_url=provider_profile.base_url,
        api_key=api_key,
        model=provider_profile.default_model,
        temperature=0.1,
        max_tokens=max_tokens or _default_max_tokens(stage_id),
        timeout_seconds=60,
    )
    if provider is None:
        return StageProbeResult(ok=False, provider_id=provider_profile.id, stage_id=stage_id, stage_type=node.type, error_code="provider_incomplete", message="Provider 配置不完整")
    probe_inputs = _probe_inputs(inputs)
    state = NovelRunState(run_id="provider-stage-probe", project_id="provider-stage-probe", workflow_id=workflow.id, inputs=probe_inputs)
    _seed_upstream_state(state, stage_id)
    prompt = PromptPlanBuilder().build(node, state, template_content="结构化探针：返回字段完整但内容尽量简短。必须返回单个 JSON object。")
    try:
        schema = None if node.type == "chapter_text" else node.output_schema
        artifact = await provider.generate_structured(prompt, task_name=node.type, context=probe_inputs, schema=schema)
    except ProviderResponseError as exc:
        failure = public_provider_failure(exc)
        return StageProbeResult(ok=False, provider_id=provider_profile.id, stage_id=stage_id, stage_type=node.type, error_code=failure.code, message=failure.message)
    validation = validate_chapter_generation(artifact) if node.type == "chapter_text" else validate_stage_artifact(node.type, artifact)
    if not validation.valid:
        return StageProbeResult(
            ok=False,
            provider_id=provider_profile.id,
            stage_id=stage_id,
            stage_type=node.type,
            schema_name=validation.schema_name,
            error_code="artifact_validation_failed",
            message="结构化产物未通过阶段合同校验",
            errors=validation.errors,
        )
    return StageProbeResult(
        ok=True,
        provider_id=provider_profile.id,
        stage_id=stage_id,
        stage_type=node.type,
        schema_name=validation.schema_name,
        message="结构化阶段探针通过",
        summary=_artifact_summary(validation.artifact),
    )


def _probe_inputs(inputs: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "title": "雾港试验",
        "theme": "旧港、记忆实验、三人追查旧案",
        "stage_configs": {
            "info": {
                "genre": "悬疑",
                "target_length": "短篇",
                "target_words_range": "1-3 万字",
                "audience": "喜欢强情节悬疑的读者",
                "core_concept": "一盘旧磁带揭开十年前记忆实验旧案。",
                "keywords": ["旧港", "记忆实验", "磁带"],
                "taboos": "不要超自然万能解释。",
                "reference_mode": "smart_search",
                "reference_summary": "无外部资料，本次只做结构化链路测试。",
            }
        },
        **(inputs or {}),
    }


def _default_max_tokens(stage_id: str) -> int:
    return {
        "info": 2200,
        "summary": 3200,
        "outline": 2800,
        "detail": 4200,
        "text": 2600,
    }.get(stage_id, 2200)


def _seed_upstream_state(state: NovelRunState, stage_id: str) -> None:
    if stage_id == "info":
        return
    story_brief = _fixture_story_brief()
    state.story_brief = {"source": "probe_fixture", "content": story_brief}
    state.artifacts["info_recommend"] = story_brief
    state.worldbuilding_state = {
        "source": "probe_fixture",
        "rules": ["雾钟是声纹证词记录装置，不是超自然力量", "蓝潮实验会改变证词可信度，但不能万能解释所有冲突"],
        "locations": ["旧港档案馆", "雾钟码头", "蓝潮实验区"],
    }
    if stage_id in {"outline", "detail", "text"}:
        state.artifacts["summary"] = _fixture_summary()
    if stage_id in {"detail", "text"}:
        state.artifacts["outline"] = _fixture_outline()
    if stage_id == "text":
        detail = _fixture_detail_outline()
        state.artifacts["detail_outline"] = detail
        state.chapter_context_packets.append(_fixture_chapter_context())


def _fixture_story_brief() -> dict[str, Any]:
    return {
        "selected_title": "雾港旧声",
        "title_candidates": ["雾港旧声", "雾钟回声", "7A-13 磁带"],
        "synopsis": "林澈修复 7A-13 旧磁带时听见求救声，和许望舒、周泊言一起重返蓝潮旧案。",
        "worldbuilding_detail": "旧港的雾钟系统记录声纹证词，蓝潮实验曾篡改关键证词。",
        "characters": [
            {"name": "林澈", "identity": "声纹修复师", "motivation": "查父亲与蓝潮旧案", "relations": "与许望舒合作", "growth_direction": "从回避到追查"},
            {"name": "许望舒", "identity": "调查记者", "motivation": "证明旧案真实存在", "relations": "推动林澈面对证据", "growth_direction": "从追报道到保护证人"},
            {"name": "周泊言", "identity": "幸存者", "motivation": "确认自己被改写的证词", "relations": "既是向导也是风险源", "growth_direction": "从隐瞒到交出证据"},
        ],
        "relationships": [
            {"source": "林澈", "target": "许望舒", "relation": "调查同盟", "strength": 0.68},
            {"source": "林澈", "target": "周泊言", "relation": "互相试探", "strength": 0.52},
            {"source": "许望舒", "target": "周泊言", "relation": "采访者与证人", "strength": 0.61},
        ],
        "tags": ["悬疑", "旧港", "记忆实验"],
        "downstream_constraints": ["关系变化要有证据推进", "三章完成第一层真相揭示"],
        "risk_notes": ["避免把记忆篡改写成万能解释"],
    }


def _fixture_summary() -> dict[str, Any]:
    return {
        "one_liner": "旧磁带让林澈、许望舒和周泊言发现，旧港失踪案与蓝潮实验有关。",
        "full_synopsis": "林澈修复 7A-13 磁带时听见十年前求救声。许望舒带来采访材料，周泊言承认幸存者身份。三人追查后确认雾钟记录的是被筛选过的证词回声，并公开第一批声纹档案。",
        "act_structure": [
            {"title": "磁带入局", "goal": "建立旧磁带与旧案关联", "turn": "求救声说出尚未发生的地点"},
            {"title": "蓝潮追查", "goal": "确认证词被技术性篡改", "turn": "幸存者关系网浮现"},
            {"title": "雾钟公开", "goal": "公开证据并保留后续动机", "turn": "父亲签章进入主线"},
        ],
        "core_conflict": "个人记忆与公共档案冲突，真相公开会威胁港务利益链。",
        "character_arcs": [
            {"name": "林澈", "arc": "从修复档案到公开档案", "pressure": "父亲可能参与蓝潮", "next": "判断亲情与证据边界"},
            {"name": "许望舒", "arc": "从报道旧案转向保护证人", "pressure": "采访材料可能害证人暴露", "next": "建立证人保护策略"},
        ],
        "key_turns": [
            {"label": "7A-13 母带", "detail": "求救声与林澈私人记忆重叠"},
            {"label": "缺页名单", "detail": "删改日志和幸存者名单不一致"},
            {"label": "雾钟提前响起", "detail": "系统在无人操作时播放新的证词回声"},
        ],
        "ending_resolution": "公开第一层真相，同时留下父亲签章和备用电源两条长线。",
        "consistency_checks": ["雾钟机制符合 info 硬设定", "三位主角都有主动选择"],
    }


def _fixture_outline() -> dict[str, Any]:
    return {
        "volumes": [
            {
                "title": "第一卷：7A-13 母带",
                "chapter_range": "第1-3章",
                "volume_goal": "完成旧案入口、三人结盟和第一层真相揭示。",
                "rhythm": "悬念递进，第三章爆点",
                "opening": "林澈修复磁带，听见十年前求救声。",
                "development": "许望舒带来删改日志，周泊言暴露幸存者身份。",
                "midpoint": "蓝潮证据证明证词被筛选。",
                "climax": "雾钟在无人操作下提前响起。",
                "resolution": "三人公开第一批声纹档案。",
                "character_progression": [{"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "公开证据可能暴露证人", "change": "从回避旧案到主动追查父亲签章", "impact": "下一卷继续校准证据与信任边界"}],
                "world_reveal": [{"anchor": "雾钟", "reveal": "它是声纹证词记录装置", "rule": "只能记录和筛选既有声纹", "impact": "后续细纲必须保留技术证据链"}],
                "foreshadow_plan": [{"name": "父亲签章", "status": "投放", "chapter_range": "第3章", "note": "卷尾露出但不解释"}],
            }
        ]
    }


def _fixture_detail_outline() -> dict[str, Any]:
    return {
        "chapters": [
            {
                "chapter": "第1章",
                "pov": "林澈",
                "scene": "旧港档案馆",
                "goal": "修复 7A-13 磁带",
                "entry_state": "林澈只想完成普通委托",
                "conflict": "磁带底噪出现他的名字",
                "stakes": "私人记忆被卷入旧案",
                "fact_reveals": [{"anchor": "雾钟", "fact": "7A-13 母带存在", "impact": "旧案获得物证入口"}],
                "foreshadow": [{"name": "父亲签章", "status": "投放", "note": "保留签章来源疑问"}],
                "character_shift": {"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "母带可能被封存", "motivation": "确认求救声来源", "change": "开始怀疑自己的记忆", "impact": "主动保留并追查证据"},
                "hook": "求救声来自十年前",
                "continuity_notes": "承接 info 中声纹档案设定",
                "wiki_candidates": [{"title": "7A-13 母带", "fact": "保存十年前声纹证词", "source_anchor": "雾钟"}],
            }
        ]
    }


def _fixture_chapter_context() -> ChapterContextPacket:
    return ChapterContextPacket(
        chapter="第1章",
        chapter_index=1,
        chapter_kind="first",
        story_brief="旧港声纹档案修复师林澈接到编号 7A-13 的旧磁带，旧案重新打开。",
        summary="第一卷需要完成旧案入口、三人结盟和第一层真相揭示。",
        volume_goal="完成旧案入口、三人结盟和第一层真相揭示。",
        chapter_outline="林澈在旧港档案馆修复 7A-13 磁带，底噪出现他的名字，并投放父亲签章伏笔。",
        previous_chapter_summary="",
        character_state={
            "林澈": {"status": "回避旧案但被磁带拉回调查"},
            "许望舒": {"status": "尚未正式入场，掌握未公开采访材料"},
        },
        open_foreshadows=[
            {"name": "7A-13 母带", "status": "待投放"},
            {"name": "父亲签章", "status": "待投放"},
        ],
        world_rules=["雾钟是声纹证词记录装置，不是超自然力量", "记忆实验不能万能解释所有冲突"],
    )


def _artifact_summary(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return {"artifact_type": type(artifact).__name__}
    summary: dict[str, Any] = {"keys": sorted(artifact.keys())}
    if "selected_title" in artifact:
        summary.update(
            {
                "selected_title": artifact.get("selected_title"),
                "title_candidates": len(artifact.get("title_candidates", [])),
                "characters": len(artifact.get("characters", [])),
                "relationships": len(artifact.get("relationships", [])),
            }
        )
    if "volumes" in artifact:
        summary["volumes"] = len(artifact.get("volumes", []))
    if "chapters" in artifact:
        summary["chapters"] = len(artifact.get("chapters", []))
    if "content" in artifact:
        summary["content_chars"] = len(str(artifact.get("content") or ""))
    if "wiki_writebacks" in artifact:
        summary["wiki_writebacks"] = len(artifact.get("wiki_writebacks", []))
    if "foreshadow_updates" in artifact:
        summary["foreshadow_updates"] = len(artifact.get("foreshadow_updates", []))
    return summary
