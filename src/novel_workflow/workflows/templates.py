from __future__ import annotations

from novel_workflow.workflows.schemas import (
    InputField,
    MemoryPolicy,
    ModelSettings,
    ProviderProfile,
    QualityPolicy,
    StageConfig,
    VariantPolicy,
    GenerationBudget,
    CanvasLayout,
    CanvasNodePosition,
    CanvasViewport,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from novel_workflow.workflows.prompt_templates import (
    INFO_RECOMMEND_STAGE_PROMPT,
    default_prompt_templates,
)


REAL_PROVIDER_ID = "openai-compatible"
IMAGE_PROVIDER_ID = "openai-compatible-image"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_IMAGE_MODEL = "gpt-image-1.5"


STAGE_GENERATION_BUDGETS: dict[str, GenerationBudget] = {
    "info": GenerationBudget(
        target_chars=2200,
        min_chars=1400,
        max_chars=3200,
        max_tokens=4600,
        description="立项 Story Brief 要建立完整人物基线（5-9 名、含阵营与关系语义）和风格规格，同时保持可人工定稿。",
    ),
    "summary": GenerationBudget(
        target_chars=1200,
        min_chars=1200,
        max_chars=2800,
        max_tokens=3600,
        description="参考出版 synopsis 常用 500-1000 英文词范围，中文梗概需覆盖完整故事、人物变化与结局。",
    ),
    "outline": GenerationBudget(
        target_chars=1400,
        min_chars=1400,
        max_chars=3600,
        max_tokens=4200,
        description="按卷输出 beat board，小字段完整，不让后端再从长文拆节拍。",
    ),
    "detail": GenerationBudget(
        target_chars=1800,
        min_chars=1800,
        max_chars=4800,
        max_tokens=5200,
        description="三章细纲需覆盖 POV、目标、冲突、事实、伏笔、人物变化和连续性。",
    ),
    "text": GenerationBudget(
        target_chars=1500,
        min_chars=1500,
        max_chars=3200,
        max_tokens=4200,
        description="首轮每章控制在中等篇幅，兼顾正文质感与用量成本。",
    ),
    "cover": GenerationBudget(
        target_chars=500,
        min_chars=500,
        max_chars=1400,
        max_tokens=2200,
        description="先由文本模型生成封面 brief、prompt 和候选计划，再由独立图片 Provider 生成并落盘真实资产。",
    ),
}


def generation_budget_for_stage(stage_id: str) -> GenerationBudget:
    return STAGE_GENERATION_BUDGETS.get(
        stage_id,
        GenerationBudget(target_chars=900, min_chars=500, max_chars=1600, max_tokens=2000, description="保持字段完整且克制。"),
    )

STAGE_OUTPUT_SCHEMAS = {
    "info": {
        "selected_title": "string",
        "title_candidates": "string[]",
        "synopsis": "string",
        "worldbuilding_detail": "string",
        "characters": "Array<{ name, identity, background, motivation, relations, tier, faction, faction_stance, growth_direction }>",
        "relationships": "Array<{ source, target, relation, kind, polarity, strength }>",
        "tags": "string[]",
        "downstream_constraints": "string[]",
        "risk_notes": "string[]",
        "voice_spec": "{ narration, rhythm, banned_words[], cliche_slots[], per_character: Array<{ character, habits, catchphrase, speech_register, never_says }> }",
    },
    "summary": {
        "one_liner": "string",
        "full_synopsis": "string",
        "act_structure": "Array<{ title, goal, turn }>",
        "core_conflict": "string",
        "character_arcs": "Array<{ name, arc, pressure, next }>",
        "key_turns": "Array<{ label, detail }>",
        "ending_resolution": "string",
        "consistency_checks": "string[]",
    },
    "outline": {
        "volumes": "Array<{ title, chapter_range, volume_goal, rhythm, opening, development, midpoint, climax, resolution, new_characters: Array<{ name, role, tier, faction, faction_stance, stance, relation_to_protagonist }>, character_progression: Array<{ character, related_to, relation, kind, polarity, strength, pressure, change, impact }>, world_reveal: Array<{ anchor, reveal, rule, impact }>, foreshadow_plan: Array<{ name, status: 投放|推进|回收|延后, chapter_range, note }> }>",
    },
    "detail": {
        "chapters": "Array<{ chapter, pov, scene, goal, entry_state, conflict, stakes, fact_reveals: Array<{ anchor, fact, impact }>, foreshadow: Array<{ name, status, note }>, character_shift: { character, related_to, relation, kind, polarity, strength, pressure, motivation, change, impact }, hook, continuity_notes, wiki_candidates: Array<{ title, fact, source_anchor, claim_key }>, new_npcs: Array<{ name, role, faction, note }> }>",
    },
    "text": {
        "schema_version": "number",
        "status": "running|completed",
        "target_chapters": "number",
        "context_packet": "ChapterContextPacket",
        "context_packets": "ChapterContextPacket[]",
        "chapter_deltas": "Array<{ chapter, delta }>",
        "chapters": "Array<{ id, title, generated_title, content, words, status, version, commit_signature, summary, summary_dirty, context_packet, wiki_writebacks, character_shift, foreshadow_updates, quality_report, quality_recheck, model_review, writeback_proposal, revision_history, version_history }>",
        "quality_reports": "QualityReport[]",
        "wiki_writebacks": "Array<{ target, fact, claim_key, source_chapter }>",
        "chapter_summaries": "Array<{ chapter, summary }>",
    },
    "cover": {
        "brief": "string",
        "visual_keywords": "string[]",
        "composition": "string",
        "copy_suggestions": "string[]",
        "prompt": "string",
        "candidates": "Array<{ id, composition, palette, quality_summary }>",
        "selected_candidate_id": "string",
        "asset_generation": "{ status, total, ready_count, failed_count, provider_profile_id, model, size, quality, updated_at }",
    },
    "export": {
        "manifest": "Array<{ name, format, status }>",
        "formats": "string[]",
        "chapters": "Array<{ id, title, words, status, content }>",
        "metadata": "Record<string, string>",
        "cover_asset": "{ candidate_id, asset_id, sha256, mime_type, width, height, size_bytes, image_url }",
        "validation": "Record<string, string>",
        "package_status": "{ kind, name, ready }",
    },
}


def default_workflow() -> WorkflowDefinition:
    providers = default_provider_profiles()
    prompts = default_prompt_templates()
    nodes = [
        WorkflowNode(
            id="info",
            type="info_recommend",
            label="创作立项定稿",
            params={"prompt": INFO_RECOMMEND_STAGE_PROMPT},
            output_key="info_recommend",
            output_schema=STAGE_OUTPUT_SCHEMAS["info"],
            memory_policy=MemoryPolicy(read=False, write=True, scope="project", kinds=["worldbuilding", "topology"]),
            input_schema=info_recommend_input_schema(),
            prompt_template_id="prompt-info",
            provider_profile_id=REAL_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, max_tokens=generation_budget_for_stage("info").max_tokens),
            generation_budget=generation_budget_for_stage("info"),
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
            output_schema=STAGE_OUTPUT_SCHEMAS["summary"],
            memory_policy=MemoryPolicy(read=True, write=True, scope="project", kinds=["worldbuilding", "topology"]),
            input_schema=[
                InputField(key="target_words", label="梗概字数", type="number", default=1200),
                InputField(key="structure", label="结构偏好", type="select", default="起承转合", options=["起承转合", "三幕式", "悬疑递进", "群像交织"]),
                InputField(key="ending_direction", label="结局方向", default="真相公开但保留余味"),
            ],
            prompt_template_id="prompt-summary",
            provider_profile_id=REAL_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, max_tokens=generation_budget_for_stage("summary").max_tokens),
            generation_budget=generation_budget_for_stage("summary"),
            variant_policy=VariantPolicy(enabled=False, candidate_count=1),
        ),
        WorkflowNode(
            id="outline",
            type="outline",
            label="分卷大纲",
            input_refs=["summary"],
            params={"volumes": 1},
            output_key="outline",
            output_schema=STAGE_OUTPUT_SCHEMAS["outline"],
            memory_policy=MemoryPolicy(read=True, write=True, scope="volume", kinds=["worldbuilding", "topology", "outline"]),
            input_schema=[
                InputField(key="volume_count", label="卷数", type="number", default=1),
                InputField(key="chapters_per_volume", label="每卷章节数", type="number", default=3),
                InputField(key="conflict_density", label="冲突密度", type="select", default="中高", options=["平缓", "中等", "中高", "高压"]),
            ],
            prompt_template_id="prompt-outline",
            provider_profile_id=REAL_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, max_tokens=generation_budget_for_stage("outline").max_tokens),
            generation_budget=generation_budget_for_stage("outline"),
            variant_policy=VariantPolicy(enabled=False, candidate_count=1),
        ),
        WorkflowNode(
            id="detail",
            type="detail_outline",
            label="章节细纲",
            input_refs=["outline"],
            params={"chapters": 3},
            output_key="detail_outline",
            output_schema=STAGE_OUTPUT_SCHEMAS["detail"],
            memory_policy=MemoryPolicy(read=True, write=True, scope="chapter", kinds=["worldbuilding", "topology", "outline", "chapter"]),
            input_schema=[
                InputField(key="chapter_count", label="细纲章节数", type="number", default=3),
                InputField(key="must_include", label="每章必须包含", type="tags", default=["目标", "冲突", "伏笔", "章末钩子"]),
            ],
            prompt_template_id="prompt-detail",
            provider_profile_id=REAL_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, max_tokens=generation_budget_for_stage("detail").max_tokens),
            generation_budget=generation_budget_for_stage("detail"),
            variant_policy=VariantPolicy(enabled=False, candidate_count=1),
        ),
        WorkflowNode(
            id="text",
            type="chapter_text",
            label="正文生成",
            input_refs=["detail_outline"],
            params={"chapters": 3, "target_chars": 1800},
            output_key="chapters",
            output_schema=STAGE_OUTPUT_SCHEMAS["text"],
            memory_policy=MemoryPolicy(read=True, write=True, scope="chapter", kinds=["worldbuilding", "topology", "outline", "chapter"]),
            input_schema=[
                InputField(key="chapter_words", label="单章字数", type="number", default=1200),
                InputField(key="max_chapters_to_generate", label="本轮生成章节数", type="number", default=3, help="每轮先生成这几章，定稿后可以继续写下一批。"),
                InputField(key="pov", label="叙事视角", type="select", default="第三人称有限视角", options=["第一人称", "第三人称有限视角", "多视角"]),
                InputField(key="batch_generate", label="批量生成章节", type="boolean", default=True),
                InputField(
                    key="enable_version_compare",
                    label="多版本比对",
                    type="boolean",
                    default=False,
                    help="每章生成多个候选并自动评审优选，用量按候选数成倍增加；仅在平衡模式自动生效，精细模式只在你主动换稿时生成候选。",
                ),
                InputField(
                    key="version_candidate_count",
                    label="候选版本数",
                    type="number",
                    default=2,
                    help="自动比对使用的候选数量，范围 1-3 版。",
                ),
                InputField(key="judge_provider_profile_id", label="评审服务", type="select", default="inherit", options=["inherit", REAL_PROVIDER_ID], help="默认由正文服务担任评审。"),
                InputField(key="judge_model", label="评审模型", default=DEFAULT_MODEL),
                InputField(key="compare_dimensions", label="比对维度", type="tags", default=["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"]),
            ],
            prompt_template_id="prompt-text",
            provider_profile_id=REAL_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, temperature=0.82, max_tokens=generation_budget_for_stage("text").max_tokens),
            generation_budget=generation_budget_for_stage("text"),
            variant_policy=VariantPolicy(enabled=False, candidate_count=1, retry_on_fail=False),
            quality_policy=QualityPolicy(min_score=0.84, retry_on_fail=True, checks=["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"]),
        ),
        WorkflowNode(
            id="cover",
            type="cover_image",
            label="AI 封面",
            input_refs=["info_recommend", "summary", "outline", "detail_outline"],
            output_key="cover",
            output_schema=STAGE_OUTPUT_SCHEMAS["cover"],
            memory_policy=MemoryPolicy(read=False, write=False, scope="project", kinds=["cover"]),
            input_schema=[
                InputField(key="cover_style", label="封面风格", type="select", default="电影感悬疑", options=["电影感悬疑", "国风幻想", "赛博科幻", "青春现实"]),
                InputField(key="aspect_ratio", label="比例", type="select", default="2:3", options=["2:3"]),
                InputField(key="candidate_count", label="图片候选数", type="number", default=3, help="每个候选对应一次独立图片生成，范围 1-4。"),
                InputField(key="image_quality", label="图片质量", type="select", default="medium", options=["low", "medium", "high"]),
                InputField(key="asset_retry_limit", label="失败重试上限", type="number", default=2, help="仅对失败候选显式重试，范围 0-3。"),
                InputField(key="image_budget_usd", label="图片费用上限（USD）", type="number", default=0, help="0 表示仅限制调用次数；填写后会在调用前校验预计费用。"),
            ],
            prompt_template_id="prompt-cover",
            provider_profile_id=REAL_PROVIDER_ID,
            image_provider_profile_id=IMAGE_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, temperature=0.62, max_tokens=generation_budget_for_stage("cover").max_tokens),
            generation_budget=generation_budget_for_stage("cover"),
        ),
        WorkflowNode(
            id="export",
            type="export_artifact",
            label="导出产物",
            input_refs=["info_recommend", "summary", "outline", "detail_outline", "chapters", "cover"],
            output_key="export",
            output_schema=STAGE_OUTPUT_SCHEMAS["export"],
            memory_policy=MemoryPolicy(read=False, write=False, scope="project"),
            provider_profile_id=REAL_PROVIDER_ID,
            model_settings=ModelSettings(model=DEFAULT_MODEL, max_tokens=1200),
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
            image_provider_profile_id=node.image_provider_profile_id,
            fallback_targets=node.fallback_targets,
            image_fallback_targets=node.image_fallback_targets,
            model_settings=node.model_settings,
            prompt_template_id=node.prompt_template_id,
            output_schema=node.output_schema,
            memory_policy=node.memory_policy,
            quality_policy=node.quality_policy,
            variant_policy=node.variant_policy,
            generation_budget=node.generation_budget,
        )
        for node in nodes
    }
    edges = [
        WorkflowEdge(id="e-info-summary", source="info", target="summary"),
        WorkflowEdge(id="e-summary-outline", source="summary", target="outline"),
        WorkflowEdge(id="e-outline-detail", source="outline", target="detail"),
        WorkflowEdge(id="e-detail-text", source="detail", target="text"),
        WorkflowEdge(id="e-detail-cover", source="detail", target="cover"),
        WorkflowEdge(id="e-text-export", source="text", target="export"),
        WorkflowEdge(id="e-cover-export", source="cover", target="export"),
    ]
    return WorkflowDefinition(
        id="default-novel-workflow",
        name="长篇小说生产线工作流",
        # Reseeding compares version + content digest (bootstrap.seed_defaults),
        # so template edits reach existing installs even without a version bump.
        # The version string stays as a human-readable changelog marker.
        version="1.0.5-parallel-delivery",
        global_inputs=[
            InputField(key="title", label="项目标题", required=True, default="雾港旧声"),
        ],
        provider_profiles=providers,
        prompt_templates=prompts,
        stage_configs=stage_configs,
        quality_mode="balanced",
        canvas_layout=default_canvas_layout(),
        nodes=nodes,
        edges=edges,
    )


def materialize_workflow_for_execution(workflow: WorkflowDefinition) -> WorkflowDefinition:
    materialized = workflow.model_copy(deep=True)
    default_provider = next(
        (profile for profile in materialized.provider_profiles if profile.is_global_default and profile.kind == "openai-compatible"),
        None,
    )
    if default_provider is None:
        default_provider = next((profile for profile in materialized.provider_profiles if profile.kind == "openai-compatible"), None)
    if default_provider is None:
        return materialized
    default_image_provider = next(
        (profile for profile in materialized.provider_profiles if profile.is_global_default and profile.kind == "openai-compatible-image"),
        None,
    ) or next((profile for profile in materialized.provider_profiles if profile.kind == "openai-compatible-image"), None)

    for node in materialized.nodes:
        if node.provider_profile_id == "inherit" and default_provider.kind == "openai-compatible":
            node.provider_profile_id = default_provider.id
            node.model_settings.model = default_provider.default_model
        stage_config = materialized.stage_configs.get(node.id)
        if stage_config is not None and stage_config.provider_profile_id == "inherit":
            stage_config.provider_profile_id = default_provider.id
            stage_config.model_settings.model = default_provider.default_model
        if node.type == "cover_image" and not node.image_provider_profile_id and default_image_provider is not None:
            node.image_provider_profile_id = default_image_provider.id
        if stage_config is not None and node.type == "cover_image" and not stage_config.image_provider_profile_id and default_image_provider is not None:
            stage_config.image_provider_profile_id = default_image_provider.id
    return materialized


def default_provider_profiles() -> list[ProviderProfile]:
    return [
        ProviderProfile(
            id=REAL_PROVIDER_ID,
            name="文本接口",
            kind="openai-compatible",
            template_id="openai-compatible-text",
            base_url="",
            api_key_env="NOVEL_LLM_API_KEY",
            default_model=DEFAULT_MODEL,
            model_options=[DEFAULT_MODEL],
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


def info_recommend_input_schema() -> list[InputField]:
    return [
        InputField(key="genre", label="题材", type="select", required=True, default="悬疑", options=["悬疑", "玄幻", "都市", "科幻", "言情", "历史", "现实", "轻小说"], hint="决定读者预期与后续阶段的类型惯例校验。"),
        InputField(key="target_length", label="目标篇幅", type="select", required=True, default="长篇", options=["短篇", "中篇", "长篇", "系列长篇"]),
        InputField(key="target_words_range", label="目标字数区间", type="select", required=True, default="80-120 万字", options=["1-3 万字", "5-10 万字", "20-40 万字", "80-120 万字", "120 万字以上"], hint="篇幅只选这一次，目标规模会随字数区间自动确定。"),
        InputField(key="audience", label="目标读者", required=True, default="偏好强情节、悬念推进、人物关系清晰的网文读者", hint="写给谁看：平台、口味与期待的阅读体验。", placeholder="例如：偏好强冲突、快节奏反转的悬疑读者"),
        InputField(key="core_concept", label="核心创意/冲突", type="textarea", required=True, default="旧港多年前的记忆实验留下旧案回声，主角追查真相时发现自己最可信的记忆也被改写。", hint="立项只需要一个能撑起全书的核心冲突，人物与世界观随后生成。", placeholder="一句话说清冲突：谁+想要什么+被什么阻止"),
        InputField(key="keywords", label="关键词", type="tags", required=True, default=["旧港", "记忆实验", "群像", "旧案"], hint="3-6 个题材、氛围或元素词，同时用于参考检索。", placeholder="例如：孤岛、双时间线、身份互换"),
        InputField(key="taboos", label="禁忌/不要出现", type="textarea", required=True, default="避免无动机黑化、机械降神、纯设定堆砌、套路化系统开局和无关恋爱线抢主线。", hint="不想出现的桥段与元素，会作为硬约束进入每个生成阶段。", placeholder="例如：不要机械降神、不要无动机黑化"),
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
            "info": CanvasNodePosition(x=20, y=168),
            "summary": CanvasNodePosition(x=214, y=168),
            "outline": CanvasNodePosition(x=408, y=168),
            "detail": CanvasNodePosition(x=602, y=168),
            "text": CanvasNodePosition(x=796, y=168),
            "cover": CanvasNodePosition(x=990, y=168),
            "export": CanvasNodePosition(x=1184, y=168),
            "wiki-layer": CanvasNodePosition(x=324, y=-96),
            "quality-layer": CanvasNodePosition(x=708, y=452),
        },
        viewport=CanvasViewport(x=0, y=0, zoom=0.76),
        crosscutting_visible=True,
        locked=False,
    )
