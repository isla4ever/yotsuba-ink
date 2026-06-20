from __future__ import annotations

from novel_workflow.workflows.schemas import (
    InputField,
    MemoryPolicy,
    ModelSettings,
    PromptTemplate,
    ProviderProfile,
    QualityPolicy,
    StageConfig,
    VariantPolicy,
    CanvasLayout,
    CanvasNodePosition,
    CanvasViewport,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)


def default_workflow() -> WorkflowDefinition:
    providers = default_provider_profiles()
    prompts = default_prompt_templates()
    nodes = [
        WorkflowNode(
            id="info",
            type="info_recommend",
            label="创作立项定稿",
            params={"prompt": _INFO_RECOMMEND_STAGE_PROMPT},
            output_key="info_recommend",
            memory_policy=MemoryPolicy(read=False, write=True, scope="project", kinds=["worldbuilding", "topology"]),
            input_schema=info_recommend_input_schema(),
            prompt_template_id="prompt-info",
            provider_profile_id="mock-text",
            variant_policy=VariantPolicy(enabled=False, candidate_count=1, retry_on_fail=False),
            quality_policy=QualityPolicy(
                min_score=0.82,
                retry_on_fail=True,
                require_human_review=False,
                checks=["Brief 完整度", "题材匹配", "受众匹配", "世界观可延展性", "参考资料吸收", "禁忌遵守", "模板味风险"],
            ),
        ),
        WorkflowNode(
            id="summary",
            type="summary",
            label="全书梗概",
            input_refs=["info_recommend"],
            params={"prompt": "基于已定稿 Story Brief 生成完整梗概。"},
            output_key="summary",
            memory_policy=MemoryPolicy(read=True, write=True, scope="project", kinds=["worldbuilding", "topology"]),
            input_schema=[
                InputField(key="target_words", label="梗概字数", type="number", default=1200),
                InputField(key="structure", label="结构偏好", type="select", default="起承转合", options=["起承转合", "三幕式", "悬疑递进", "群像交织"]),
                InputField(key="ending_direction", label="结局方向", default="真相公开但保留余味"),
            ],
            prompt_template_id="prompt-summary",
            provider_profile_id="mock-text",
            variant_policy=VariantPolicy(enabled=False, candidate_count=1),
        ),
        WorkflowNode(
            id="outline",
            type="outline",
            label="分卷大纲",
            input_refs=["summary"],
            params={"volumes": 3},
            output_key="outline",
            memory_policy=MemoryPolicy(read=True, write=True, scope="volume", kinds=["worldbuilding", "topology", "outline"]),
            input_schema=[
                InputField(key="volume_count", label="卷数", type="number", default=3),
                InputField(key="chapters_per_volume", label="每卷章节数", type="number", default=8),
                InputField(key="conflict_density", label="冲突密度", type="select", default="中高", options=["平缓", "中等", "中高", "高压"]),
            ],
            prompt_template_id="prompt-outline",
            provider_profile_id="mock-text",
            variant_policy=VariantPolicy(enabled=False, candidate_count=1),
        ),
        WorkflowNode(
            id="detail",
            type="detail_outline",
            label="章节细纲",
            input_refs=["outline"],
            params={"chapters": 6},
            output_key="detail_outline",
            memory_policy=MemoryPolicy(read=True, write=True, scope="chapter", kinds=["worldbuilding", "topology", "outline", "chapter"]),
            input_schema=[
                InputField(key="chapter_count", label="细纲章节数", type="number", default=6),
                InputField(key="must_include", label="每章必须包含", type="tags", default=["目标", "冲突", "伏笔", "章末钩子"]),
            ],
            prompt_template_id="prompt-detail",
            provider_profile_id="mock-text",
            variant_policy=VariantPolicy(enabled=False, candidate_count=1),
        ),
        WorkflowNode(
            id="text",
            type="chapter_text",
            label="正文生成",
            input_refs=["detail_outline"],
            params={"chapters": 3, "target_chars": 1800},
            output_key="chapters",
            memory_policy=MemoryPolicy(read=True, write=True, scope="chapter", kinds=["worldbuilding", "topology", "outline", "chapter"]),
            input_schema=[
                InputField(key="chapter_words", label="单章字数", type="number", default=2500),
                InputField(key="pov", label="叙事视角", type="select", default="第三人称有限视角", options=["第一人称", "第三人称有限视角", "多视角"]),
                InputField(key="batch_generate", label="批量生成章节", type="boolean", default=True),
                InputField(key="enable_version_compare", label="自动版本比对", type="boolean", default=True),
                InputField(key="version_candidate_count", label="候选版本数", type="number", default=2),
                InputField(key="judge_provider_profile_id", label="评审 Provider", type="select", default="inherit", options=["inherit", "mock-text", "openai-compatible"]),
                InputField(key="judge_model", label="评审模型", default="mock-novel-judge"),
                InputField(key="compare_dimensions", label="比对维度", type="tags", default=["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"]),
            ],
            prompt_template_id="prompt-text",
            provider_profile_id="mock-text",
            variant_policy=VariantPolicy(enabled=True, candidate_count=2, retry_on_fail=True),
            quality_policy=QualityPolicy(min_score=0.84, retry_on_fail=True, checks=["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"]),
        ),
        WorkflowNode(
            id="cover",
            type="cover_image",
            label="AI 封面",
            input_refs=["chapters"],
            output_key="cover",
            memory_policy=MemoryPolicy(read=False, write=False, scope="project", kinds=["cover"]),
            input_schema=[
                InputField(key="cover_style", label="封面风格", type="select", default="电影感悬疑", options=["电影感悬疑", "国风幻想", "赛博科幻", "青春现实"]),
                InputField(key="aspect_ratio", label="比例", type="select", default="2:3", options=["2:3", "3:4", "1:1"]),
            ],
            prompt_template_id="prompt-cover",
            provider_profile_id="mock-image",
        ),
        WorkflowNode(
            id="export",
            type="export_artifact",
            label="导出产物",
            input_refs=["info_recommend", "summary", "outline", "detail_outline", "chapters", "cover"],
            output_key="export",
            memory_policy=MemoryPolicy(read=False, write=False, scope="project"),
            input_schema=[
                InputField(key="export_format", label="导出格式", type="select", default="Markdown + JSON", options=["Markdown + JSON", "纯 Markdown", "JSON"]),
            ],
        ),
    ]
    stage_configs = {
        node.id: StageConfig(
            node_id=node.id,
            input_schema=node.input_schema,
            provider_profile_id=node.provider_profile_id,
            model_settings=node.model_settings,
            prompt_template_id=node.prompt_template_id,
            output_schema=node.output_schema,
            memory_policy=node.memory_policy,
            quality_policy=node.quality_policy,
            variant_policy=node.variant_policy,
        )
        for node in nodes
    }
    edges = [
        WorkflowEdge(id="e-info-summary", source="info", target="summary"),
        WorkflowEdge(id="e-summary-outline", source="summary", target="outline"),
        WorkflowEdge(id="e-outline-detail", source="outline", target="detail"),
        WorkflowEdge(id="e-detail-text", source="detail", target="text"),
        WorkflowEdge(id="e-text-cover", source="text", target="cover"),
        WorkflowEdge(id="e-cover-export", source="cover", target="export"),
    ]
    return WorkflowDefinition(
        id="default-novel-workflow",
        name="长篇小说生产线工作流",
        version="0.9.0",
        global_inputs=[
            InputField(key="title", label="项目标题", required=True, default="雾港旧声"),
            InputField(key="theme", label="主题偏好", type="textarea", default="悬疑、记忆、旧港、群像"),
            InputField(key="target_length", label="目标规模", type="select", default="长篇", options=["短篇", "中篇", "长篇"]),
        ],
        provider_profiles=providers,
        prompt_templates=prompts,
        stage_configs=stage_configs,
        quality_mode="balanced",
        canvas_layout=default_canvas_layout(),
        nodes=nodes,
        edges=edges,
    )


def default_provider_profiles() -> list[ProviderProfile]:
    return [
        ProviderProfile(id="mock-text", name="演示文本模型", kind="mock", default_model="mock-novel-model", model_options=["mock-novel-model", "mock-novel-judge"]),
        ProviderProfile(id="openai-compatible", name="OpenAI Compatible", kind="openai-compatible", base_url="", api_key_env="NOVEL_LLM_API_KEY", default_model="gpt-4.1-mini", model_options=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"], is_global_default=True),
        ProviderProfile(id="mock-image", name="演示封面模型", kind="image-mock", default_model="mock-cover", model_options=["mock-cover"]),
    ]


def default_prompt_templates() -> list[PromptTemplate]:
    return [
        PromptTemplate(id="prompt-info", name="创作立项 Prompt", stage_type="info_recommend", content=_INFO_RECOMMEND_STAGE_PROMPT, variables=["genre", "audience", "keywords", "core_concept", "reference_summary"]),
        PromptTemplate(id="prompt-summary", name="梗概 Prompt", stage_type="summary", content="基于已定稿 Story Brief、世界观硬设定、人物种子和 Wiki 约束，生成全书梗概、主线、角色弧、长线伏笔和结局方向。", variables=["target_words", "structure"]),
        PromptTemplate(id="prompt-outline", name="分卷大纲 Prompt", stage_type="outline", content="基于梗概、角色弧和未回收伏笔，生成卷级目标、卷冲突、章节范围和伏笔分布，避免与世界观硬设定冲突。", variables=["volume_count", "chapters_per_volume"]),
        PromptTemplate(id="prompt-detail", name="章节细纲 Prompt", stage_type="detail_outline", content="按目标章节数逐章输出目标、承接、核心冲突、人物变化、伏笔推进、信息差和章末钩子。", variables=["chapter_count", "must_include"]),
        PromptTemplate(id="prompt-text", name="正文 Prompt", stage_type="chapter_text", content="逐章按细纲、上一章摘要、人物状态、世界观硬设定和未回收伏笔生成正文，保持动机、信息差、节奏和语言质感一致。", variables=["chapter_words", "pov"]),
        PromptTemplate(id="prompt-cover", name="封面 Prompt", stage_type="cover_image", content="根据小说信息和梗概生成封面提示词。", variables=["cover_style", "aspect_ratio"]),
    ]


def info_recommend_input_schema() -> list[InputField]:
    return [
        InputField(key="genre", label="题材", type="select", required=True, default="悬疑", options=["悬疑", "玄幻", "都市", "科幻", "言情", "历史", "现实", "轻小说"]),
        InputField(key="target_length", label="目标篇幅", type="select", required=True, default="长篇", options=["短篇", "中篇", "长篇", "系列长篇"]),
        InputField(key="target_words_range", label="目标字数区间", type="select", required=True, default="80-120 万字", options=["1-3 万字", "5-10 万字", "20-40 万字", "80-120 万字", "120 万字以上"]),
        InputField(key="audience", label="目标读者", required=True, default="偏好强情节、悬念推进、人物关系清晰的网文读者"),
        InputField(key="core_concept", label="核心创意/冲突", type="textarea", required=True, default="旧港多年前的记忆实验留下旧案回声，主角追查真相时发现自己最可信的记忆也被改写。"),
        InputField(key="keywords", label="关键词", type="tags", required=True, default=["旧港", "记忆实验", "群像", "旧案"]),
        InputField(key="taboos", label="禁忌/不要出现", type="textarea", required=True, default="避免无动机黑化、机械降神、纯设定堆砌、套路化系统开局和无关恋爱线抢主线。"),
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
            "info": CanvasNodePosition(x=420, y=20),
            "summary": CanvasNodePosition(x=420, y=160),
            "outline": CanvasNodePosition(x=420, y=300),
            "detail": CanvasNodePosition(x=420, y=440),
            "text": CanvasNodePosition(x=420, y=580),
            "cover": CanvasNodePosition(x=420, y=720),
            "export": CanvasNodePosition(x=420, y=860),
            "wiki-layer": CanvasNodePosition(x=276, y=302),
            "quality-layer": CanvasNodePosition(x=694, y=302),
        },
        viewport=CanvasViewport(x=-10, y=18, zoom=0.72),
        crosscutting_visible=True,
        locked=False,
    )


_INFO_RECOMMEND_STAGE_PROMPT = """你是小说产品策划、类型小说编辑和故事架构师。请根据用户创作 Brief、参考资料摘要和禁忌，生成可被人工编辑定稿，并被后续梗概/大纲/细纲/正文持续约束的创作立项 Story Brief。

输出必须结构化，优先使用 Markdown 分段，并包含：
1. 标题候选：至少 5 个，说明题材定位与卖点。
2. Story Brief：一句话卖点、题材定位、目标读者、目标篇幅、商业看点。
3. 人物种子：主角、关键配角、潜在对立面，每个角色给动机、缺口、可持续冲突。
4. 世界观种子 world_seed/worldbuilding：硬设定、社会规则、关键地点/组织、不可违背约束。
5. 核心冲突与长线伏笔：列出可延展到梗概、大纲、细纲和正文的伏笔。
6. 参考风格吸收点：只吸收结构、节奏、调性，不复制具体表达和专有设定。
7. 风险与禁忌提醒：指出模板味风险、违禁风险、读者预期风险。
8. 后续梗概约束：给下一阶段必须遵守的 6-10 条约束。

要求：不要给空泛套话；世界观必须能支撑目标篇幅；人物关系要能形成后续关系网；输出应便于写入 Wiki/World Info。"""
