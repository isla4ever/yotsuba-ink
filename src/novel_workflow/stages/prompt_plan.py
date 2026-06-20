from __future__ import annotations

from typing import Any

from novel_workflow.workflows.schemas import NovelRunState, WorkflowNode


class PromptPlanBuilder:
    def build(self, node: WorkflowNode, state: NovelRunState) -> str:
        stage_config = state.inputs.get("stage_configs", {}).get(node.id, {}) if isinstance(state.inputs.get("stage_configs"), dict) else {}
        return "\n\n".join(
            [
                self._role_task(node),
                self._brief(node, state, stage_config),
                self._reference_context(node, state, stage_config),
                self._upstream(node, state),
                self._chapter_context(node, state),
                self._constraints(node, state),
                self._output_contract(node),
                self._rubric(node),
                self._guardrails(node),
            ]
        )

    def _role_task(self, node: WorkflowNode) -> str:
        tasks = {
            "info_recommend": "你是类型小说策划、商业编辑和故事架构师。目标是产出可人工定稿的创作立项 Story Brief，而不是直接进入流水线。",
            "summary": "你是长篇小说总结构编辑。目标是把已定稿 Story Brief 扩展为全书主线、冲突阶梯、角色弧、世界观揭示节奏、伏笔总账和结局承诺。",
            "outline": "你是长篇分卷策划。目标是根据目标篇幅推导合理卷数，把全书梗概拆成卷目标、章节范围、卷首钩子、卷中反转、卷尾爆点和伏笔分布。",
            "detail_outline": "你是全书章节细纲编辑。目标是先覆盖全部目标章节，再允许进入正文；每章必须给承接、目标、冲突、人物变化、伏笔推进和章末钩子。",
            "chapter_text": "你是长篇正文主笔。目标是按全书细纲逐章写作，并读取 Story Brief、梗概、卷目标、上一章摘要、上一卷结尾、人物状态、未回收伏笔和世界观硬设定。",
            "cover_image": "你是封面提示词设计师。目标是把小说气质转成可生成封面的视觉提示词。",
            "export_artifact": "你是产物整理器。目标是汇总可导出的小说资产。",
        }
        return f"## 角色任务\n{tasks.get(node.type, node.label)}"

    def _brief(self, node: WorkflowNode, state: NovelRunState, stage_config: dict[str, Any]) -> str:
        title = state.inputs.get("title") or "未命名小说"
        theme = state.inputs.get("theme") or "悬疑、成长、强情节"
        fields = []
        for field in node.input_schema:
            value = stage_config.get(field.key, state.inputs.get(field.key, field.default))
            fields.append(f"- {field.label}({field.key}): {value}")
        return f"## 输入 Brief\n- 小说标题: {title}\n- 主题/偏好: {theme}\n" + "\n".join(fields)

    def _reference_context(self, node: WorkflowNode, state: NovelRunState, stage_config: dict[str, Any]) -> str:
        if node.type != "info_recommend":
            story_brief = state.story_brief.get("content") if isinstance(state.story_brief, dict) else ""
            return f"## 定稿 Story Brief / 参考依据\n{story_brief or '沿用上游 Story Bible / Wiki 约束。'}"
        mode = stage_config.get("reference_mode") or "smart_search"
        summary = stage_config.get("reference_summary") or "暂无命中；请基于用户 Brief 自主生成原创方案。"
        mode_labels = {
            "smart_search": "智能搜索",
            "url": "指定链接",
            "knowledge_base": "上传文件 / 知识库",
        }
        return f"## 参考资料摘要\n- 参考源: {mode_labels.get(str(mode), mode)}\n{summary}"

    def _upstream(self, node: WorkflowNode, state: NovelRunState) -> str:
        previous = []
        if node.type != "info_recommend" and state.story_brief:
            previous.append(f"### approved_story_brief\n{state.story_brief.get('content')}")
        for ref in node.input_refs:
            if ref in state.artifacts:
                previous.append(f"### {ref}\n{state.artifacts[ref]}")
        return "## 上游产物\n" + ("\n".join(previous) if previous else "暂无")

    def _chapter_context(self, node: WorkflowNode, state: NovelRunState) -> str:
        if node.type != "chapter_text" or not state.chapter_context_packets:
            return "## 章节上下文包\n非正文阶段无需章节上下文包。"
        packet = state.chapter_context_packets[-1]
        return (
            "## 章节上下文包\n"
            f"- 当前章节: {packet.chapter} / {packet.chapter_kind}\n"
            f"- 所属卷目标: {packet.volume_goal or '暂无'}\n"
            f"- 当前章细纲: {packet.chapter_outline or '暂无'}\n"
            f"- 上一章摘要: {packet.previous_chapter_summary or '暂无'}\n"
            f"- 上一卷结尾: {packet.previous_volume_ending or '暂无'}\n"
            f"- 未回收伏笔: {packet.open_foreshadows or '暂无'}\n"
            f"- 世界观硬设定: {packet.world_rules or '暂无'}"
        )

    def _constraints(self, node: WorkflowNode, state: NovelRunState) -> str:
        memory = state.memory_contexts.get(node.id, {})
        hits = memory.get("hits") if isinstance(memory, dict) else None
        world = state.worldbuilding_state or {}
        character = state.character_graph.model_dump() if state.character_graph.nodes else {}
        return (
            "## Wiki / World / Character 约束\n"
            f"- Wiki 命中: {hits or '暂无'}\n"
            f"- 世界观状态: {world or '暂无'}\n"
            f"- 人物关系: {character or '暂无'}"
        )

    def _output_contract(self, node: WorkflowNode) -> str:
        contracts = {
            "info_recommend": (
                "输出可人工编辑定稿的 Story Brief：项目定位、核心卖点、世界观种子、角色种子、角色名/身份/行为边界、"
                "禁忌与必须保留元素、参考吸收、长线伏笔、结局方向、风险提示、后续梗概硬约束。只生成一版，不做候选比对。"
            ),
            "summary": (
                "输出全书梗概：一句话主线、冲突阶梯、三幕/递进结构、角色弧、世界观揭示节奏、伏笔总账、主要反转、结局承诺、"
                "分卷阶段必须遵守的约束。"
            ),
            "outline": (
                "先根据目标篇幅与字数区间推导建议卷数和每卷章节范围；再逐卷输出卷目标、卷首钩子、卷中反转、卷尾爆点、"
                "人物阶段变化、伏笔投放与回收计划。"
            ),
            "detail_outline": (
                "必须覆盖全部目标章节，章节数量不得少于配置的 chapter_count；逐章输出承接来源、章节目标、核心冲突、人物变化、"
                "伏笔推进/回收、世界观信息、章末钩子，并标注所属卷。"
            ),
            "chapter_text": (
                "输出当前章节正文，不要摘要化。首章强化钩子和核心承诺；卷首重建目标和张力；卷尾完成爆点/回收/转折；"
                "终章兑现结局承诺；普通章承接上一章摘要并推进当前章细纲。"
            ),
        }
        return f"## 输出结构\n{contracts.get(node.type, '输出结构化结果，便于后续阶段读取。')}"

    def _rubric(self, node: WorkflowNode) -> str:
        checks = node.quality_policy.checks or ["连续性", "人物一致性", "世界观冲突", "伏笔推进", "模板味"]
        return f"## 质量 Rubric\n最低分: {node.quality_policy.min_score:.2f}\n检查项: {'、'.join(checks)}"

    def _guardrails(self, node: WorkflowNode) -> str:
        return (
            "## 禁止事项\n"
            "- 不要复制参考资料的专有设定或具体表达。\n"
            "- 不要引入与已写 Wiki/World 硬设定冲突的事实。\n"
            "- 不要用空泛套话代替具体人物动机、冲突和伏笔。\n"
            "- 如果信息不足，优先补充可持续约束，而不是跳过。"
        )
