from __future__ import annotations

from novel_workflow.workflows.schemas import PromptTemplate


INFO_RECOMMEND_STAGE_PROMPT = """你是小说产品策划、类型小说编辑和故事架构师。请根据用户创作 Brief、参考资料摘要和禁忌，生成可被人工编辑定稿，并被后续梗概/大纲/细纲/正文持续约束的创作立项 Story Brief。

输出必须是结构化对象，字段直接对齐 info artifact，不要返回需要后端二次解析的 Markdown 长文。必须包含：
1. selected_title 与 title_candidates：至少 5 个书名候选。
2. synopsis：小说简介，说明题材定位、目标读者、目标篇幅和商业看点。
3. worldbuilding_detail：详细世界观，覆盖硬设定（不超过 12 条）、社会规则、关键地点/组织和不可违背约束。
4. characters：5-9 名主要角色，每个角色包含 name、identity、background（人物旧事及其与主线的隐性联系）、motivation、relations、tier（protagonist/major/supporting）、faction（阵营名）、faction_stance、growth_direction。角色阵容必须覆盖主角、对手方与关键支点人物；配角与 NPC 留给后续阶段按配额引入。
5. relationships：8-20 条关系边，每条包含 source、target、relation、kind（kinship/romance/ally/rival/superior/trade/secret/other）、polarity（positive/negative/complex/neutral）、strength。关系网必须覆盖跨阵营张力，不允许只围绕主角辐射。
6. tags：轻量题材、节奏、爽点和风格标签。
7. downstream_constraints：给 summary / outline / detail / text 必须遵守的约束。
8. voice_spec：全书风格规格——narration（人称/时态/叙事距离）、rhythm（句长与对话叙述比）、banned_words、cliche_slots，以及 per_character 主要人物语声表（habits/catchphrase/speech_register/never_says）。

要求：不要给空泛套话；世界观必须能支撑目标篇幅；人物关系要能形成可生长的大型关系网；输出应便于写入 Wiki、Worldbuilding 和 Character Graph。"""


SUMMARY_STAGE_PROMPT = """基于已定稿 Story Brief、人物关系、世界观硬设定与下游约束，返回结构化 summary artifact。

- one_liner 只概括主角、目标和核心阻力；full_synopsis 必须写清开局、升级、关键选择、代价、高潮、结局与余波，形成连续因果链，不能写成宣传简介。
- act_structure 每一幕都给出 title、goal、turn；后一幕必须由前一幕转折触发。
- core_conflict 说明主角目标、阻力系统、失败代价与时间/资源压力。
- character_arcs 只能引用已确认人物，每项完整给出 name、arc、pressure、next，并与关键转折互相印证。
- key_turns 每项给出 label、detail，说明它如何改变人物选择或故事状态；ending_resolution 必须结算核心冲突和主要人物承诺。
- consistency_checks 逐项检查人物动机、世界规则、证据链、伏笔与结局承诺；不得新增未注册人物、地点或组织。"""


OUTLINE_STAGE_PROMPT = """基于已确认梗概、Info 人物与世界观、未回收伏笔，返回结构化 outline artifact。

- volumes 的 chapter_range 必须按顺序连续、互不重叠，并覆盖配置的目标章节；volume_goal 和 rhythm 要能指导该卷取舍。
- 每卷必须完整返回 opening、development、midpoint、climax、resolution 五段节拍；每一拍由上一拍的结果推动，resolution 要结算本卷目标并为下一卷建立可执行因果。
- character_progression 必须引用已确认人物或本卷 new_characters，并完整给出关系、kind、polarity、strength、压力、变化和影响。
- new_characters 仅在确有结构职责时新增，最多 4 名且 tier 必须为 supporting，同时给出 faction、faction_stance/stance 与主角关系；不得新增主角级人物。
- world_reveal 必须引用已确认世界观原文 anchor，并给出 reveal、rule、impact；不得改写既有硬规则。
- foreshadow_plan 给出 name、status、chapter_range、note，状态只能是投放、推进、回收或延后，并能在对应章节范围实际执行。"""


DETAIL_STAGE_PROMPT = """按目标章节数返回结构化 detail_outline artifact，逐章给出可直接进入正文的施工蓝图。

- chapters 必须按顺序覆盖全部目标章节且 chapter 唯一；每章完整返回 pov、scene、goal、entry_state、conflict、stakes、hook、continuity_notes。
- 第 2 章起的 entry_state 必须由上一章 hook/结果造成；continuity_notes 要明确“承接什么、如何进入本章、向下一章交付什么”。只有字段明确标注时才允许视角转移、倒叙或时间跳切。
- 每章 fact_reveals、wiki_candidates、foreshadow 各返回 1-3 条结构对象；事实引用已确认 world anchor，Wiki 候选给出 source_anchor，伏笔状态只能是投放、推进、回收或延后。
- character_shift 完整返回 character、related_to/relation、kind、polarity、pressure、motivation、change、impact；POV 与人物变化只能引用已注册的非 NPC 人物。
- 每章可通过 new_npcs 引入最多 2 名不承担关键剧情的 NPC；不得让 NPC 承担 POV、核心反转或解决主冲突。"""


TEXT_STAGE_PROMPT = """逐章按当前 Chapter Context Packet、已确认细纲和 Voice Spec 生成一个结构化章节产物。

- 默认从上一章结果连续续写。开篇先用动作、后果、物证或人物反应兑现 previous_chapter_summary 与 transition_directive，再进入本章 entry_state；不要复述摘要，不要重新介绍故事。
- 只有细纲明确标记时才允许视角转移、倒叙或时间跳切；转换前必须给出可感知的因果、时间、地点或视角锚点，并保留上一章后果。
- 卷首先承接 previous_volume_ending 再启动 volume_goal；卷末结算本卷目标，并向 next_volume_goal 建立具体因果。
- 正文必须推进本章 goal/conflict/stakes，人物动机、信息差、世界规则、未回收伏笔和语言质感保持一致；章末 hook 必须由本章行动后果产生。
- summary 只记录本章新增事实、人物状态和未决行动，足以供下一章承接；wiki_writebacks、character_shift、foreshadow_updates 只返回本章真实发生的变化。"""


COVER_STAGE_PROMPT = """根据已定稿的小说信息、全书梗概、分卷结构和章节细纲返回结构化 cover planning artifact：封面 brief、视觉关键词、构图、文案建议、图片提示词和 3 个候选方案 metadata。封面规划在章节细纲定稿后与正文并行，不依赖全文完成；候选只返回稳定 id、构图、色板和质量说明，不得编造 image_url、Data URL 或图片已生成状态，真实图片由 ImageProvider 独立生成。"""


def default_prompt_templates() -> list[PromptTemplate]:
    return [
        PromptTemplate(id="prompt-info", name="创作立项 Prompt", stage_type="info_recommend", content=INFO_RECOMMEND_STAGE_PROMPT, variables=["genre", "audience", "keywords", "core_concept", "reference_summary"]),
        PromptTemplate(id="prompt-summary", name="梗概 Prompt", stage_type="summary", content=SUMMARY_STAGE_PROMPT, variables=["target_words", "structure"]),
        PromptTemplate(id="prompt-outline", name="分卷大纲 Prompt", stage_type="outline", content=OUTLINE_STAGE_PROMPT, variables=["volume_count", "chapters_per_volume"]),
        PromptTemplate(id="prompt-detail", name="章节细纲 Prompt", stage_type="detail_outline", content=DETAIL_STAGE_PROMPT, variables=["chapter_count", "must_include"]),
        PromptTemplate(id="prompt-text", name="正文 Prompt", stage_type="chapter_text", content=TEXT_STAGE_PROMPT, variables=["chapter_words", "pov"]),
        PromptTemplate(id="prompt-cover", name="封面 Prompt", stage_type="cover_image", content=COVER_STAGE_PROMPT, variables=["cover_style", "aspect_ratio"]),
    ]
