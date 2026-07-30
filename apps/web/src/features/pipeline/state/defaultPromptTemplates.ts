import type { PromptTemplate } from '../contracts';

export const defaultPromptTemplates: PromptTemplate[] = [
  {
    id: 'prompt-info',
    name: '创作立项 Prompt',
    stage_type: 'info_recommend',
    content: `你是小说产品策划、类型小说编辑和故事架构师。请根据用户创作 Brief、参考资料摘要和禁忌，生成可被人工编辑定稿，并被后续梗概/大纲/细纲/正文持续约束的创作立项 Story Brief。

输出必须是结构化对象，字段直接对齐 info artifact，不要返回需要后端二次解析的 Markdown 长文。必须包含 selected_title、title_candidates、synopsis、worldbuilding_detail、characters、relationships、tags、downstream_constraints、risk_notes 与 voice_spec。人物必须给出 tier、faction、faction_stance 和 growth_direction；关系必须给出 kind、polarity 与 strength。不要给空泛套话，不要把后续阶段需要的配角和 NPC 一次性塞进立项。`,
    variables: ['genre', 'audience', 'keywords', 'core_concept', 'reference_summary'],
  },
  {
    id: 'prompt-summary',
    name: '梗概 Prompt',
    stage_type: 'summary',
    content: `基于已定稿 Story Brief、人物关系、世界观硬设定与下游约束，返回结构化 summary artifact。

full_synopsis 必须写清开局、升级、关键选择、代价、高潮、结局与余波，形成连续因果链，不能写成宣传简介；act_structure 后一幕由前一幕转折触发；character_arcs 只能引用已确认人物；key_turns 要说明如何改变人物选择或故事状态；ending_resolution 结算核心冲突；consistency_checks 检查人物动机、世界规则、证据链、伏笔与结局承诺。`,
    variables: ['target_words', 'structure'],
  },
  {
    id: 'prompt-outline',
    name: '分卷大纲 Prompt',
    stage_type: 'outline',
    content: `基于已确认梗概、Info 人物与世界观、未回收伏笔，返回结构化 outline artifact。

chapter_range 必须连续、互不重叠并覆盖目标章节；每卷完整返回 opening、development、midpoint、climax、resolution，后一拍由前一拍结果推动，resolution 结算本卷目标并为下一卷建立因果。character_progression 引用已确认人物或本卷 new_characters；新增人物最多 4 名且 tier=supporting。world_reveal 引用已确认世界观 anchor；foreshadow_plan 只能使用投放、推进、回收或延后。`,
    variables: ['volume_count', 'chapters_per_volume'],
  },
  {
    id: 'prompt-detail',
    name: '章节细纲 Prompt',
    stage_type: 'detail_outline',
    content: `按目标章节数返回结构化 detail_outline artifact。第 2 章起的 entry_state 必须由上一章 hook 或结果造成；continuity_notes 明确承接内容、本章进入方式和下一章交付。只有字段明确标注时才允许视角转移、倒叙或时间跳切。每章 fact_reveals、wiki_candidates、foreshadow 各返回 1-3 条；character_shift 引用已注册非 NPC 人物；new_npcs 最多 2 名且不得承担 POV、核心反转或解决主冲突。`,
    variables: ['chapter_count', 'must_include'],
  },
  {
    id: 'prompt-text',
    name: '正文 Prompt',
    stage_type: 'chapter_text',
    content: `逐章按当前 Chapter Context Packet、已确认细纲和 Voice Spec 生成一个结构化章节产物。默认从上一章结果连续续写，开篇先用动作、后果、物证或人物反应兑现 previous_chapter_summary 与 transition_directive，再进入本章 entry_state。只有细纲明确标记时才允许视角转移、倒叙或时间跳切；卷首先承接 previous_volume_ending，卷末结算 volume_goal 并向 next_volume_goal 建立具体因果。summary 必须足以供下一章承接。`,
    variables: ['chapter_words', 'pov'],
  },
  {
    id: 'prompt-cover',
    name: '封面 Prompt',
    stage_type: 'cover_image',
    content: '根据已定稿的小说信息、全书梗概、分卷结构和章节细纲返回结构化 cover planning artifact。封面规划在章节细纲定稿后与正文并行；候选只返回稳定 id、构图、色板和质量说明，不得编造 image_url、Data URL 或图片已生成状态，真实图片由 ImageProvider 独立生成。',
    variables: ['cover_style', 'aspect_ratio'],
  },
];
