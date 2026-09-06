"""Versioned prompt and schema snapshots for Phase 32 route stages."""

from __future__ import annotations

from novel_workflow.output_contracts.phase32_route_artifacts import (
    phase32_artifact_binding,
)
from novel_workflow.output_contracts.phase32_delivery_artifacts import CoverProposal
from novel_workflow.providers.frozen_contract import prompt_digest, schema_digest
from novel_workflow.providers.phase32_contract import Phase32ProviderTaskSnapshot
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER,
)
from novel_workflow.workflows.route_compiler import CompiledRouteStage
from novel_workflow.workflows.route_specs import CreationRouteId, ProviderTaskKind


_TRANSPORT_TASK_NAMES: dict[ProviderTaskKind, str] = {
    "screenplay_brief": "brief",
    "novel_brief": "brief",
    "character_bible": "cast",
    "beat_board": "spine",
    "story_map": "spine",
    "book_architecture": "spine",
    "volume_architecture": "volumes",
    "scene_deck": "detail",
    "section_plan": "detail",
    "rolling_detail": "detail",
    "screenplay_draft": "text",
    "short_prose_unit": "text",
    "chapter": "text",
    "cover": "cover",
}


_TASK_INSTRUCTIONS: dict[ProviderTaskKind, str] = {
    "screenplay_brief": (
        "建立可拍摄的剧本样片立项。把用户创意压缩为单一、可见、可执行的冲突，"
        "先给出与核心冲突直接相关的正式中文片名 title，禁止待定、未命名、路线名或编号占位；"
        "明确观众承诺与结尾效果；sample_type 必须是面向作者的具体样片类型，"
        "禁止复制 screenplay_sample、brief 或任何 route/stage ID。audience_promise 必须说明"
        "本故事独有的认知参与或情绪兑现，不能只写类型惯例。visible_conflict 必须同时交代"
        "具体对抗者或阻力、台面行动、期限、失败后果与不可逆选择。ending_effect 必须说明"
        "结尾揭示、主角向谁交付/暴露/保留什么、因此失去什么、换来什么，以及留下的后续问题。"
        "不要写剧情大纲，不要用抽象主题替代台面行动。"
    ),
    "novel_brief": (
        "建立小说立项合同。先给出与故事承诺直接相关的正式中文书名 title，禁止待定、未命名、"
        "路线名或编号占位；明确故事前提、读者承诺、主题问题、不可随意破坏的世界规则、"
        "结局方向和叙事声音；不要提前生成章节或具名人物注册表。"
    ),
    "character_bible": (
        "只登记推动当前故事所必需的人物。每个人物必须有可区分的欲望、利害、限制、"
        "声音与变化范围；关系必须落在已登记 subject_ref 上。必须逐项遵守冻结上下文中的"
        "epistemic_custody：Brief、Story Map 与 Book Architecture 是已接受规划，不是 Canon，"
        "也不是指控、隐秘动机或后果已经成立的证据。开放问题、怀疑、未来结果和风险不得写成"
        "人物事实；只能保留为人物认知、可见压力、可能后果或有待后续证实的变化条件。"
        "凡 Brief 或 Story Map 中作为行动者、对手或被追索对象并在多个 anchor 中持续出现的角色，"
        "必须登记为一个 character。上游职能标签若只指向一个身份必须保持未知的持续角色，"
        "display_name 应原样保留该标签；若‘失踪者’、‘证人’等标签实际代表多个会独立出场、"
        "承担不同证据链、对白或人物弧的个体，必须在 Cast 阶段拆成不同 subject_ref，并为每个主体"
        "提供可区分的作者工作名。创建工作名属于人物规划，不得借命名补写未证实的身份揭示、"
        "隐秘动机、罪责、关系或既定结局。不得把多个独立主体合并成一个集合角色来规避注册。"
    ),
    "beat_board": (
        "规划台面可见的决策节拍。每个节拍都要写清戏剧任务、外部压力、人物决定与结果，"
        "避免把心理解释或主题判断伪装成行动。除 beat_ref、setup_or_payoff_refs 等稳定引用外，"
        "dramatic_job、visible_pressure、character_decision、outcome 与 timing_hint 的自然语言内容"
        "必须使用简体中文，不得输出英文剧情说明。character_decision 不得填写‘无决定’、"
        "‘No decision’或同义占位；尾声拍也必须写明前一决定如何延续为可见行动，否则应合并到"
        "前一节拍。setup_or_payoff_refs 只能填写稳定 ASCII 引用，"
        "例如 setup_abnormal_signal 或 payoff_chen_mo_arrival；禁止填写 setup: 异常信号、"
        "payoff: 人物出现等带冒号标签或中文说明。"
    ),
    "scene_deck": (
        "把已接受节拍转成可拍摄场景序列。每场只描述地点时间、出场人物、可见目标、"
        "对抗与结果，并给出柔性页数目标。每个 scene 必须是一个连续地点和时间中的"
        "单一可拍摄行动单元；不得在 heading 或 location_and_time 中合并多个地点、"
        "时间段或转场，遇到地点/时间变化必须拆成新的 scene。heading 必须只包含一个"
        "地点和一个时间标记；禁止使用斜杠、分号、‘随后’、‘然后’、‘转至’或‘切到’"
        "连接两个地点/时间。先按动作发生的连续边界拆分场景，再填写每场的 outcome；"
        "不要把电话、抵达、进门或离开等转场压进同一个 scene。"
    ),
    "screenplay_draft": (
        "只撰写当前 scene_ref 的规范剧本块。必须从 frozen_context.sequential_unit.current_scene"
        " 读取并逐字使用 heading、location_and_time、cast_subject_refs、visible_goal、"
        "opposition 和 outcome；第一块必须是该场景的唯一 scene_heading，后续不得再出现"
        "scene_heading。全部 action、dialogue 和 parenthetical 必须发生在这个连续地点/时间"
        "内，只能使用该场景的冻结人物；不得合并其他 scene、跳转地点或时间、提前消费后续"
        "场景、改写 frozen outcome，或补写未规划人物、场景、结果。每个 block 只能有 kind 和 text；"
        "只有 dialogue 或 parenthetical 才能额外填写 speaker_ref，且必须是当前 scene 的冻结 subject_ref；"
        "scene_heading、action、transition 必须省略 speaker_ref，绝不能填空字符串。对白文本也必须"
        "放在 text 字段，禁止 dialogue_text、content、block_type 或任何其它别名；不要输出 schema 外字段。"
    ),
    "story_map": (
        "为短中篇建立有限故事锚点：开场压力、选择或揭示、后果、承诺推进与收束状态。"
        "不要强行量化因果评分，也不要在 Cast 前创建稳定人物 ID。"
        "每个 anchor 至少填写一个 promise_ref；promise_ref 是当前 Story Map 新建的稳定 ASCII "
        "承诺引用，使用短小的 lower_snake_case 或 kebab-case，例如 promise_missing_voice。"
        "同一条跨锚点承诺必须复用同一个 ref，禁止用空数组绕过承诺追踪，也禁止把中文说明、"
        "anchor_ref、stage id 或 Artifact ref 当作 promise_ref。JSON 中每个 anchor 都必须显式带上"
        "promise_refs，例如 \"promise_refs\":[\"promise_missing_voice\"]，不能省略该键。"
    ),
    "section_plan": (
        "把故事地图和人物圣经转成连续的章节或段落计划。每个单元必须有戏剧任务、POV、"
        "场景负载、handoff 与柔性字符预算。每个 unit 至少引用一个已接受 Story Map 中的 "
        "promise_ref，所有 Story Map promise_ref 必须至少被一个 unit 承接；不得新造、改名或"
        "遗漏承诺引用。JSON 中每个 unit 都必须显式带上 promise_refs，例如"
        " \"promise_refs\":[\"promise_missing_voice\"]，不能省略该键。"
    ),
    "short_prose_unit": (
        "只撰写当前短中篇正文单元，承接上一 handoff 并兑现当前计划；不改写已接受前文，"
        "不擅自改变结局方向或人物注册表。frozen Cast 的 display_name 是人物唯一有效称谓；"
        "不得给已登记人物另造姓名、化名或具名别称；也不得给未登记的行动者、被追索对象或匿名角色"
        "创造新的姓名，必须继续使用 frozen Cast 的职能标签。若 display_name 是‘失踪记者’等职能标签，"
        "正文继续使用该标签，不能擅自命名。只兑现 current_unit.promise_refs 所投影的 Story Map "
        "锚点，并保持 previous_unit_tail 中已接受的身份与事实连续。"
    ),
    "book_architecture": (
        "建立长篇 Book/Part 层级合同，冻结长期承诺、进入与退出状态、转折和未决义务。"
        "不要恢复扁平 cause/change 脊柱，也不要提前写卷册和章节。"
        "parts 内的 part_ref、promise_refs 和 turning_point_refs 是当前 Artifact 新建的稳定 ASCII 引用，"
        "必须使用短小的 lower_snake_case 或 kebab-case，例如 part_core、promise_archive、"
        "turning_point_reveal；不得把上游 Artifact ref、stage id 或完整哈希当作 promise_ref。"
        "每个 Part 至少包含一个 promise_ref 和一个 turning_point_ref，ordinal 必须从 1 连续递增。"
    ),
    "volume_architecture": (
        "在已接受 Book/Part 与人物边界内规划卷册。每卷要有独立承诺、冲突、高潮、闭合、"
        "Part 归属和稳定引用。"
    ),
    "rolling_detail": (
        "只规划当前有界滚动窗口，给出连续章节施工图、场景、handoff 与下一窗口入口状态；"
        "不得重排已接受前缀。窗口必须严格使用 window_ref、ordinal、volume_refs、chapters、"
        "entry_state、handoff、next_window_entry_state；章节必须严格使用 chapter_ref、ordinal、"
        "volume_ref、title、pov_subject_ref、cast_subject_refs、dramatic_job、entry_state、scenes、"
        "conflict、stakes、exit_state、hook、handoff、length_hint；场景必须严格使用 scene_ref、"
        "ordinal、location、time_context、cast_subject_refs、goal、opposition、outcome。"
        "volume_ref、volume_refs、pov_subject_ref 和 cast_subject_refs 必须逐字使用冻结上下文中已有的"
        "Volume/Cast 引用；window_ref、chapter_ref、scene_ref 是当前 Artifact 新建的稳定 ASCII 引用，"
        "例如 window_main、chapter_01、scene_01_01。禁止使用 summary、characters、time 等旧别名，"
        "禁止把 location 与 time 合并为一个字段；每个场景保持单一连续地点和时间，ordinal 从 1 连续递增。"
        "每个章节的 title、dramatic_job、entry_state、conflict、stakes、exit_state、hook、handoff "
        "只能写该章 cast_subject_refs 对应的 display_name；handoff 若要承接下一章尚未进入本章范围的人物，"
        "必须用‘下一份报告’等职能描述，不能提前写其姓名。每个场景的 location、time_context、goal、"
        "opposition、outcome 只能写该场景 cast_subject_refs 对应的 display_name；章节允许的角色不自动等于"
        "每个场景允许的角色。不得仅为容纳越界姓名而把未参与本章或本场景的 subject_ref 填入范围。"
        "当 scale_profile.profile_kind 为 continuity_acceptance 时，必须只输出一个 Window，且该 Window "
        "只引用 Volumes 中 ordinal 最小的第一卷、总计恰好十二章；每章只保留一至两个必要场景，"
        "所有自然语言字段用一句简洁中文表达，优先保证 JSON 完整闭合，禁止用冗长复述耗尽输出上限。"
    ),
    "chapter": (
        "只撰写当前长篇章节，遵守 Book/Part/Volume/Window、人物与上一章 handoff；"
        "不回写 Canon/Wiki，不修改未来规划。frozen Cast 的 display_name 是人物唯一有效称谓；"
        "只允许使用当前 chapter.cast_subject_refs 已登记人物的 display_name，不得给已登记人物另造姓名、"
        "化名或具名别称，也不得给未登记的行动者、被追索对象或匿名角色创造新的姓名。若 display_name "
        "是‘失踪者’、‘匿名委托人’等职能标签，正文必须继续使用该标签；任何身份揭示都必须先通过"
        "已接受 Cast 修订进入人物注册表，不能在正文中临时命名。不要输出‘注：’、括号说明、提示词复述、"
        "作者旁白或‘此处不使用姓名’等元话语；直接写故事正文。不得出现任何不在冻结 Cast display_name"
        "列表中的中文人名。若冻结列表只有‘失踪者’或‘匿名委托人’，必须重复该职能标签：正确写法是"
        "‘我必须找到失踪者’，错误写法是‘我必须找到苏晚’；宁可重复标签，也不能为了让句子自然而创造"
        "两至四字姓名。previous_chapter_tail 只是不可变更的连续性参考；当前章必须从它之后开始，"
        "不得复制、改写、摘要或重演其中已完成的观察、动作与结尾意象。已建立的日期、时间和事件"
        "顺序不得重置。证据、工具和测量精度必须符合可观测条件，无法确认的信息必须保持未知或概率表达。"
        "length_hint 是软目标；应优先生成不少于其百分之六十的有效新内容，禁止用重复或凑字数达标。"
    ),
    "cover": (
        "生成与已接受正文一致的封面视觉 Brief 和候选方向。每个候选提供可访问替代文本、"
        "构图说明和独立图片提示词；不得输出或虚构资产引用，真实 asset_ref 由系统在图片落盘后绑定。"
    ),
}


_TASK_PROMPT_REVISIONS: dict[ProviderTaskKind, int] = {
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


def build_phase32_provider_task_snapshot(
    route_id: CreationRouteId,
    stage: CompiledRouteStage,
) -> Phase32ProviderTaskSnapshot:
    """Freeze the exact task instructions and current Artifact JSON schema."""

    task_kind = stage.provider_task_kind
    if task_kind is None:
        raise ValueError(f"Deterministic stage {stage.stage_id} has no Provider task")
    artifact = phase32_artifact_binding(route_id, stage.stage_id)
    schema_model = CoverProposal if task_kind == "cover" else artifact.model_type
    schema = schema_model.model_json_schema(mode="validation")
    prompt = "\n".join(
        (
            "你是 Yotsuba Ink Phase 32 的专业中文创作节点。",
            (
                f"冻结上下文中的 {PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER}。"
                f"当前产品只接受 {PHASE32_CREATION_LANGUAGE}；值为 {PHASE32_CREATION_LANGUAGE} 时，"
                "Artifact 中所有面向作者的自然语言字段必须使用简体中文。"
                "JSON Schema key、枚举值、稳定 ref 与 code-owned metadata 继续使用合同规定的 ASCII，"
                "不得翻译成中文标签。"
            ),
            _TASK_INSTRUCTIONS[task_kind],
            "只生成当前阶段唯一核心 Artifact；不得输出运行状态、版本、进度、审阅、回执或 UI 字段。",
            "稳定引用使用简短小写英文、数字、下划线或连字符；只引用冻结上下文中存在的上游事实。",
            "字数、页数、节拍与结构数量是柔性创作目标，但目标单位和值必须服从冻结规模合同。",
        )
    )
    prompt_revision = _TASK_PROMPT_REVISIONS[task_kind]
    return Phase32ProviderTaskSnapshot(
        provider_task_kind=task_kind,
        artifact_kind=stage.artifact_kind,
        transport_task_name=_TRANSPORT_TASK_NAMES[task_kind],
        prompt_template_id=(
            f"prompt.phase32.{route_id}.{stage.stage_id}.v{prompt_revision}"
        ),
        prompt_template=prompt,
        prompt_template_digest=prompt_digest(prompt),
        output_schema=schema,
        output_schema_digest=schema_digest(schema),
    )


__all__ = [
    "PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER",
    "build_phase32_provider_task_snapshot",
]
