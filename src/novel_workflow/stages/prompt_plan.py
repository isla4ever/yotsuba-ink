from __future__ import annotations

import json
from typing import Any

from novel_workflow.stages.prompt_layers import (
    PROMPT_CHAR_BUDGET,
    PromptPlan,
    PromptSection,
    assemble_user,
    entity_state,
    hard_constraints,
    voice_spec_section,
)
from novel_workflow.stages.prompt_output_contracts import (
    compact_contract_for_node,
    compact_output_budget,
)
from novel_workflow.workflows.schemas import NovelRunState, WorkflowNode


class PromptPlanBuilder:
    """Builds the layered prompt plan (system = L0 + contract; user = L1-L5).

    build() renders system and user into one string joined by
    PROMPT_SYSTEM_SPLIT so existing single-prompt provider interfaces keep
    working; OpenAI-compatible adapters split it back into real messages.
    """

    def build(self, node: WorkflowNode, state: NovelRunState, *, template_content: str = "") -> str:
        return self.build_plan(node, state, template_content=template_content).render()

    def build_plan(
        self,
        node: WorkflowNode,
        state: NovelRunState,
        *,
        template_content: str = "",
        char_budget: int = PROMPT_CHAR_BUDGET,
    ) -> PromptPlan:
        stage_config = state.inputs.get("stage_configs", {}).get(node.id, {}) if isinstance(state.inputs.get("stage_configs"), dict) else {}
        system = "\n\n".join(
            [
                self._role_task(node),
                hard_constraints(node, state),
                self._output_contract(node, stage_config),
                self._guardrails(node),
            ]
        )
        sections = [
            PromptSection(1, "task", self._template(template_content)),
            PromptSection(1, "rubric", self._rubric(node)),
            PromptSection(2, "brief", self._brief(node, state, stage_config)),
            PromptSection(2, "upstream", self._upstream(node, state)),
            PromptSection(2, "chapter_context", self._chapter_context(node, state)),
            PromptSection(3, "entities", entity_state(node, state)),
            PromptSection(4, "voice", voice_spec_section(node, state)),
            PromptSection(5, "reference", self._reference_context(node, state, stage_config)),
        ]
        user, dropped = assemble_user(sections, char_budget=char_budget)
        return PromptPlan(system=system, user=user, dropped_layers=dropped)

    def _template(self, template_content: str) -> str:
        return f"## 阶段 Prompt 模板\n{template_content.strip()}" if template_content.strip() else "## 阶段 Prompt 模板\n使用默认阶段任务。"

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
            f"- 所属卷: {packet.volume_title or '未命名卷'} / {packet.volume_chapter_range or '范围待定'}\n"
            f"- 所属卷目标: {packet.volume_goal or '暂无'}\n"
            f"- 下一卷目标: {packet.next_volume_goal or '暂无'}\n"
            f"- 当前章细纲: {packet.chapter_outline or '暂无'}\n"
            f"- 上一章摘要: {packet.previous_chapter_summary or '暂无'}\n"
            f"- 上一卷结尾: {packet.previous_volume_ending or '暂无'}\n"
            f"- 叙事衔接指令: {packet.transition_directive or '默认连续续写，不自行跳切'}\n"
            f"- 未回收伏笔: {packet.open_foreshadows or '暂无'}\n"
            f"- 世界观硬设定: {packet.world_rules or '暂无'}"
        )

    def _output_contract(self, node: WorkflowNode, stage_config: dict[str, Any]) -> str:
        schema_text = json.dumps(compact_contract_for_node(node), ensure_ascii=False, indent=2)
        budget = compact_output_budget(node, stage_config)
        if node.type == "chapter_text":
            return (
                "## 输出结构\n"
                "只返回 JSON object，不要 Markdown、不要解释、不要代码块。当前调用只生成一个章节，不返回整本 chapters 数组。\n"
                f"{budget}\n"
                f"{schema_text}"
            )
        return (
            "## 输出结构\n"
            "只返回 JSON object，不要 Markdown、不要解释、不要代码块。字段必须完整，数组项必须包含 schema 中的必填字段。\n"
            f"{budget}\n"
            f"{schema_text}"
        )

    def _rubric(self, node: WorkflowNode) -> str:
        checks = node.quality_policy.checks or ["连续性", "人物一致性", "世界观冲突", "伏笔推进", "模板味"]
        return f"## 质量 Rubric\n最低分: {node.quality_policy.min_score:.2f}\n检查项: {'、'.join(checks)}"

    def _guardrails(self, node: WorkflowNode) -> str:
        chapter_guardrail = (
            "\n- 正文默认沿上一章结果连续续写；只有细纲明确标注时才允许视角转移、倒叙或时间跳切。"
            "\n- 发生视角、场景或时间转换时，必须先给出可感知的因果/时空锚点；禁止把新章写成与前文无关的重新开局。"
            "\n- 开篇先兑现叙事衔接指令：用动作、后果、物证或人物反应连接上一章结果与本章进入状态，不要复述上一章摘要。"
            "\n- 卷首先呈现上一卷结局造成的后果再启动本卷目标；卷末必须结算本卷目标，并向下一卷建立可执行因果。"
            if node.type == "chapter_text" else ""
        )
        return (
            "## 禁止事项\n"
            "- 不要复制参考资料的专有设定或具体表达。\n"
            "- 不要引入与已写 Wiki/World 硬设定冲突的事实。\n"
            "- 不要用空泛套话代替具体人物动机、冲突和伏笔。\n"
            "- 不要为了解决剧情问题临时发明新角色；超出阶段配额的新增会被系统阻断。\n"
            "- 如果信息不足，优先补充可持续约束，而不是跳过。"
            f"{chapter_guardrail}"
        )
