from __future__ import annotations

from novel_workflow.workflows.schemas import (
    InputField,
    ModelSettings,
    ProviderProfile,
    GenerationBudget,
    CanvasLayout,
    CanvasNodePosition,
    CanvasViewport,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from novel_workflow.workflows.prompt_templates import default_prompt_templates
from novel_workflow.workflows.workflow_ids import (
    DEFAULT_WORKFLOW_ID,
    OFFICIAL_BALANCED_WORKFLOW_ID,
    OFFICIAL_DEEP_WORKFLOW_ID,
    OFFICIAL_FAST_WORKFLOW_ID,
)


DEEPSEEK_PROVIDER_ID = "provider-deepseek-text"
IMAGE_PROVIDER_ID = "openai-compatible-image"
DEEPSEEK_FLASH_MODEL = "deepseek-v4-flash"
DEEPSEEK_PRO_MODEL = "deepseek-v4-pro"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
SPINE_PLANNING_TEMPERATURE = 0.45
CAST_PLANNING_TEMPERATURE = 0.55
STAGE_GENERATION_BUDGETS: dict[str, GenerationBudget] = {
    "brief": GenerationBudget(
        max_tokens=4600,
        description="创作立项 Story Brief 冻结题材承诺、世界规则、主题问题、结局承诺与叙事声音。",
    ),
    "cast": GenerationBudget(
        max_tokens=10000,
        description="全局 Role Demand 按动态人物硬上限预留响应空间，人物档案按冻结主体分组生成并建立关系。",
    ),
    "spine": GenerationBudget(
        max_tokens=8000,
        description="按动态章节容量输出精简因果 turns、结局和开放问题；不是散文梗概，也不提前分章或编排人物行为。",
    ),
    "volumes": GenerationBudget(
        max_tokens=6000,
        description="按系统冻结卷数与 Story Spine 的自然闭合输出卷合同；卷名与边界由本阶段冻结，章数槽位由代码分配。",
    ),
    "detail": GenerationBudget(
        max_tokens=6000,
        description="按 Spine 因果边界和 Provider 输出容量拆成叙事段；每章只规划必要场景、变化与下一章交接。",
    ),
    "text": GenerationBudget(
        max_tokens=6000,
        description="按冻结场景顺序逐场生成；场景按戏剧负载使用滚动字符区间，整章命中质量档位长度合同，越界最多三次有界重写。",
    ),
    "cover": GenerationBudget(
        max_tokens=2200,
        description="先由文本模型生成封面 brief、prompt 和候选计划，再由独立图片 Provider 生成并落盘真实资产。",
    ),
}


def generation_budget_for_stage(stage_id: str) -> GenerationBudget:
    return STAGE_GENERATION_BUDGETS.get(
        stage_id,
        GenerationBudget(max_tokens=2000, description="保持字段完整且克制。"),
    )


def default_workflow() -> WorkflowDefinition:
    return official_workflow("balanced")


def official_workflows() -> list[WorkflowDefinition]:
    return [
        official_workflow("fast"),
        official_workflow("balanced"),
        official_workflow("deep"),
    ]


def _model_for_stage(quality_mode: str, stage_id: str) -> str:
    if stage_id == "export":
        return ""
    if quality_mode == "fast":
        return DEEPSEEK_FLASH_MODEL
    if quality_mode == "deep":
        return DEEPSEEK_PRO_MODEL
    if quality_mode == "balanced":
        return (
            DEEPSEEK_PRO_MODEL
            if stage_id in {"brief", "spine", "cast", "volumes", "detail", "text"}
            else DEEPSEEK_FLASH_MODEL
        )
    raise ValueError(f"Unknown official quality mode: {quality_mode}")


def official_workflow(quality_mode: str) -> WorkflowDefinition:
    metadata = {
        "fast": (
            OFFICIAL_FAST_WORKFLOW_ID,
            "DeepSeek 极速创作流水线",
        ),
        "balanced": (
            OFFICIAL_BALANCED_WORKFLOW_ID,
            "DeepSeek 平衡创作流水线",
        ),
        "deep": (
            OFFICIAL_DEEP_WORKFLOW_ID,
            "DeepSeek 精细创作流水线",
        ),
    }
    if quality_mode not in metadata:
        raise ValueError(f"Unknown official quality mode: {quality_mode}")
    workflow_id, workflow_name = metadata[quality_mode]
    providers = default_provider_profiles()
    prompts = default_prompt_templates()
    nodes = [
        WorkflowNode(
            id="brief",
            type="brief",
            label="创作立项定稿",
            input_schema=brief_input_schema(),
            prompt_template_id="prompt-brief",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            model_settings=ModelSettings(model=_model_for_stage(quality_mode, "brief"), max_tokens=generation_budget_for_stage("brief").max_tokens),
            generation_budget=generation_budget_for_stage("brief"),
        ),
        WorkflowNode(
            id="spine",
            type="spine",
            label="故事脊柱",
            input_schema=[
                InputField(key="structure", label="结构偏好", type="select", default="自适应因果链", options=["自适应因果链", "悬疑递进", "群像交织"]),
                InputField(key="ending_direction", label="结局方向", default="真相公开但保留余味"),
            ],
            prompt_template_id="prompt-spine",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            model_settings=ModelSettings(
                model=_model_for_stage(quality_mode, "spine"),
                temperature=SPINE_PLANNING_TEMPERATURE,
                max_tokens=generation_budget_for_stage("spine").max_tokens,
            ),
            generation_budget=generation_budget_for_stage("spine"),
        ),
        WorkflowNode(
            id="cast",
            type="cast",
            label="人物圣经",
            input_schema=[],
            prompt_template_id="prompt-cast",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            model_settings=ModelSettings(
                model=_model_for_stage(quality_mode, "cast"),
                temperature=CAST_PLANNING_TEMPERATURE,
                max_tokens=generation_budget_for_stage("cast").max_tokens,
            ),
            generation_budget=generation_budget_for_stage("cast"),
        ),
        WorkflowNode(
            id="volumes",
            type="volumes",
            label="分卷架构",
            input_schema=[
                InputField(key="conflict_density", label="冲突密度", type="select", default="中高", options=["平缓", "中等", "中高", "高压"]),
            ],
            prompt_template_id="prompt-volumes",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            model_settings=ModelSettings(model=_model_for_stage(quality_mode, "volumes"), max_tokens=generation_budget_for_stage("volumes").max_tokens),
            generation_budget=generation_budget_for_stage("volumes"),
        ),
        WorkflowNode(
            id="detail",
            type="detail",
            label="章节施工图",
            input_schema=[
                InputField(key="must_include", label="每章必须包含", type="tags", default=["目标", "冲突", "伏笔", "章末钩子"]),
            ],
            prompt_template_id="prompt-detail",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            model_settings=ModelSettings(model=_model_for_stage(quality_mode, "detail"), temperature=0.30, max_tokens=generation_budget_for_stage("detail").max_tokens),
            generation_budget=generation_budget_for_stage("detail"),
        ),
        WorkflowNode(
            id="text",
            type="text",
            label="正文生成",
            input_schema=[
                InputField(key="pov", label="叙事视角", type="select", default="第三人称有限视角", options=["第一人称", "第三人称有限视角", "多视角"]),
            ],
            prompt_template_id="prompt-text",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            model_settings=ModelSettings(model=_model_for_stage(quality_mode, "text"), temperature=0.82, max_tokens=generation_budget_for_stage("text").max_tokens),
            generation_budget=generation_budget_for_stage("text"),
        ),
        WorkflowNode(
            id="cover",
            type="cover",
            label="AI 封面",
            input_schema=[
                InputField(key="cover_style", label="封面风格", type="select", default="电影感悬疑", options=["电影感悬疑", "国风幻想", "赛博科幻", "青春现实"]),
                InputField(key="image_size", label="图片尺寸", type="select", default="1024x1536", options=["1024x1536"]),
                InputField(key="candidate_count", label="图片候选数", type="number", default=3, help="每个候选对应一次独立图片生成，范围 1-4。"),
                InputField(key="image_quality", label="图片质量", type="select", default="medium", options=["low", "medium", "high"]),
            ],
            prompt_template_id="prompt-cover",
            provider_profile_id=DEEPSEEK_PROVIDER_ID,
            image_provider_profile_id=IMAGE_PROVIDER_ID,
            model_settings=ModelSettings(model=_model_for_stage(quality_mode, "cover"), temperature=0.62, max_tokens=generation_budget_for_stage("cover").max_tokens),
            generation_budget=generation_budget_for_stage("cover"),
        ),
        WorkflowNode(
            id="export",
            type="export",
            label="导出产物",
            provider_profile_id="",
            model_settings=ModelSettings(
                model="",
                temperature=0,
                max_tokens=0,
                top_p=1,
                timeout_seconds=0,
            ),
            input_schema=[
                InputField(key="export_format", label="导出格式", type="select", default="zip", options=["zip", "md", "json"]),
                InputField(key="author", label="作者", type="text", default=""),
                InputField(key="version_note", label="版本说明", type="text", default=""),
            ],
        ),
    ]
    stage_order = ("brief", "spine", "cast", "volumes", "detail", "text", "cover", "export")
    nodes = sorted(nodes, key=lambda node: stage_order.index(node.id))
    edges = [
        WorkflowEdge(id="e-brief-spine", source="brief", target="spine"),
        WorkflowEdge(id="e-spine-cast", source="spine", target="cast"),
        WorkflowEdge(id="e-cast-volumes", source="cast", target="volumes"),
        WorkflowEdge(id="e-volumes-detail", source="volumes", target="detail"),
        WorkflowEdge(id="e-detail-text", source="detail", target="text"),
        WorkflowEdge(id="e-detail-cover", source="detail", target="cover"),
        WorkflowEdge(id="e-text-export", source="text", target="export"),
        WorkflowEdge(id="e-cover-export", source="cover", target="export"),
    ]
    return WorkflowDefinition(
        architecture_version="phase27-vnext",
        id=workflow_id,
        name=workflow_name,
        version="29.34.0-first-pass-causal-planning",
        is_template=True,
        global_inputs=[],
        provider_profiles=providers,
        prompt_templates=prompts,
        quality_mode=quality_mode,
        canvas_layout=default_canvas_layout(),
        nodes=nodes,
        edges=edges,
    )


def materialize_workflow_for_execution(workflow: WorkflowDefinition) -> WorkflowDefinition:
    materialized = workflow.model_copy(deep=True)
    for node in materialized.nodes:
        if node.provider_profile_id == "inherit":
            raise ValueError(f"Stage {node.id} must select an explicit Provider")
    return materialized


def default_provider_profiles() -> list[ProviderProfile]:
    return [
        ProviderProfile(
            id=DEEPSEEK_PROVIDER_ID,
            name="DeepSeek 官方文本",
            kind="openai-compatible",
            template_id="deepseek-text",
            base_url="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            default_model=DEEPSEEK_PRO_MODEL,
            model_options=[DEEPSEEK_PRO_MODEL, DEEPSEEK_FLASH_MODEL],
            is_global_default=True,
        ),
        ProviderProfile(
            id=IMAGE_PROVIDER_ID,
            name="图片接口",
            kind="openai-compatible-image",
            template_id="openai-compatible-image",
            base_url="",
            api_key_env="NOVEL_IMAGE_API_KEY",
            default_model=DEFAULT_IMAGE_MODEL,
            model_options=[DEFAULT_IMAGE_MODEL],
            is_global_default=True,
        ),
    ]


def brief_input_schema() -> list[InputField]:
    return [
        InputField(key="genre", label="题材", type="select", required=False, default="自动判断", options=["自动判断", "悬疑", "玄幻", "都市", "科幻", "言情", "历史", "现实", "轻小说"], hint="默认从创作想法判断；手动选择时作为类型惯例约束。"),
        InputField(key="narrative_profile", label="叙事角色", type="select", required=True, default="故事建筑师", options=["故事建筑师", "现场观察者", "心理戏剧家", "悬念导演", "群像编年者", "意象织造者"], hint="选择贯穿全书的观察与表达策略；角色 Prompt 只读，可在首次准备中查阅。"),
        InputField(key="word_target_soft", label="全书字符目标", type="number", required=False, default=100000, hint="去除空白后统计；细纲定稿后按每章场景负载分配正文目标。"),
        InputField(key="turn_target_override", label="锁定脊柱转折数", type="number", required=False, default=None, hint="仅精细模式生效，且必须落在本书章长容量动态推导的区间内。"),
        InputField(key="audience", label="目标读者", required=False, default="偏好强情节、悬念推进、人物关系清晰的网文读者", hint="可选；留空时由创作立项根据想法判断。", placeholder="例如：偏好强冲突、快节奏反转的悬疑读者"),
        InputField(key="core_concept", label="核心创意/冲突", type="textarea", required=True, default="旧港多年前的记忆实验留下旧案回声，主角追查真相时发现自己最可信的记忆也被改写。", hint="立项只需要一个能撑起全书的核心冲突；世界规则在本阶段形成，人物职责与关系在下一阶段冻结。", placeholder="一句话说清冲突：谁+想要什么+被什么阻止"),
        InputField(key="keywords", label="关键词", type="tags", required=False, default=["旧港", "记忆实验", "群像", "旧案"], hint="可选；留空时从创作想法提炼，可用于参考检索。", placeholder="例如：孤岛、双时间线、身份互换"),
        InputField(key="taboos", label="禁忌/不要出现", type="textarea", required=False, default="避免无动机黑化、机械降神、纯设定堆砌、套路化系统开局和无关恋爱线抢主线。", hint="可选；填写后作为贯穿生成阶段的硬约束。", placeholder="例如：不要机械降神、不要无动机黑化"),
        InputField(key="reference_mode", label="参考源模式", type="select", required=True, default="smart_search", options=["smart_search", "url", "knowledge_base"]),
        InputField(key="reference_keywords", label="参考关键词", type="tags", required=False, default=["长篇悬疑", "记忆", "群像", "伏笔"]),
        InputField(key="reference_query_intent", label="参考检索意图", type="textarea", required=False, default="检索旧港、记忆实验、群像悬疑结构的参考材料；只提炼结构、节奏、题材约束，不返回可照搬桥段。"),
        InputField(key="reference_urls", label="指定链接", type="tags", required=False, default=[]),
        InputField(key="knowledge_base_doc_ids", label="知识库文档", type="tags", required=False, default=[]),
        InputField(key="enable_web_search", label="智能搜索使用联网", type="boolean", required=False, default=True),
        InputField(key="reference_summary", label="参考资料摘要", type="textarea", required=False, default=""),
    ]


def default_canvas_layout() -> CanvasLayout:
    return CanvasLayout(
        nodes={
            "brief": CanvasNodePosition(x=20, y=168),
            "spine": CanvasNodePosition(x=214, y=168),
            "cast": CanvasNodePosition(x=408, y=168),
            "volumes": CanvasNodePosition(x=602, y=168),
            "detail": CanvasNodePosition(x=796, y=168),
            "text": CanvasNodePosition(x=990, y=168),
            "cover": CanvasNodePosition(x=1184, y=168),
            "export": CanvasNodePosition(x=1378, y=168),
            "wiki-layer": CanvasNodePosition(x=480, y=-96),
            "quality-layer": CanvasNodePosition(x=900, y=452),
        },
        viewport=CanvasViewport(x=0, y=0, zoom=0.76),
        crosscutting_visible=True,
        locked=False,
    )
