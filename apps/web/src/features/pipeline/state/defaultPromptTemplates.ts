import type { PromptTemplate } from '../contracts';

type PromptStageId = Exclude<PromptTemplate['stage_type'], 'export'>;

export const promptMaterialKeys: Record<PromptStageId, string[]> = {
  info: ['project_brief', 'book_scale_plan', 'source_pack', 'revision_request'],
  characters: ['book_scale_plan', 'story_brief', 'revision_request'],
  summary: ['book_scale_plan', 'story_brief', 'character_bible', 'revision_request'],
  outline: ['book_scale_plan', 'story_brief', 'character_bible', 'summary', 'target_volume', 'revision_request'],
  detail: ['book_scale_plan', 'story_brief', 'character_bible', 'summary', 'outline', 'obligation_registry', 'target_chapters', 'revision_request'],
  text: ['book_scale', 'story_constraints', 'character_bible', 'summary_commitments', 'volume_plan', 'chapter_plan', 'previous_handoff', 'previous_accepted_chapter', 'revision_request'],
  cover: ['story', 'cast', 'narrative_arc', 'volume_objectives', 'chapter_motifs', 'revision_request'],
};

export const defaultPromptTemplates: PromptTemplate[] = [
  {
    id: 'prompt-info',
    name: '创作立项 Prompt',
    stage_type: 'info',
    content: `你是类型小说立项编辑。只返回 StoryBriefArtifact：title、premise、story_promise、world_rules、thematic_question、ending_promise、voice 与 cast_requirements。人物职责只写需求槽位，不在本阶段注册人物；禁止返回额外字段。`,
    variables: [...promptMaterialKeys.info],
  },
  {
    id: 'prompt-characters',
    name: '人物圣经 Prompt',
    stage_type: 'characters',
    content: `你是人物编排编辑。根据已确认 Story Brief 冻结 CharacterBibleArtifact：主角、重要配角、功能角色的职责/关系/弧线/首次出现窗口，以及必要 NPC 槽位。每个关系必须引用已注册 character id；后续阶段不得自行新增人物。只返回合同字段，不写 UI 状态或自评分。`,
    variables: [...promptMaterialKeys.characters],
  },
  {
    id: 'prompt-summary',
    name: '梗概 Prompt',
    stage_type: 'summary',
    content: `你是长篇小说因果编辑。基于已定稿 Story Brief 与 Character Bible 返回 SummaryArtifact 的 beats、climax、resolution、character_outcomes。character_outcomes 只能引用冻结 character_id，并覆盖全部主角与重要配角；只返回合同字段。`,
    variables: [...promptMaterialKeys.summary],
  },
  {
    id: 'prompt-outline',
    name: '分卷大纲 Prompt',
    stage_type: 'outline',
    content: `你是长篇小说节奏架构师。基于已确认 SummaryArtifact 与 Character Bible 返回 OutlineArtifact。章节数量和区间严格服从 BookScalePlan；所有人物只能引用 character_id，不得新增人物。`,
    variables: [...promptMaterialKeys.outline],
  },
  {
    id: 'prompt-detail',
    name: '章节施工图 Prompt',
    stage_type: 'detail',
    content: `你是章节施工编辑。基于已确认 Summary、Outline、Character Bible 返回 DetailArtifact。每章只写 purpose、pov_character_id、scenes、obligations、handoff；章节 id/number 必须严格匹配 BookScalePlan，义务引用只能从 obligation_registry 选择，不得创建新人物、Wiki 或 Canon 写回。`,
    variables: [...promptMaterialKeys.detail],
  },
  {
    id: 'prompt-text',
    name: '正文 Prompt',
    stage_type: 'text',
    content: `你是成熟的类型小说作者。只返回 chapter_id、title、content、author_status，不得返回由 LangGraph 运行时持有的 version_id。正文 content 必须自然收束，author_status 固定为 candidate；只能引用冻结 Detail 与 Character Bible，不得新增人物，不做正文阶段 RAG 检索，不做自动删改或 Wiki/Canon 写回。`,
    variables: [...promptMaterialKeys.text],
  },
  {
    id: 'prompt-cover',
    name: '封面 Prompt',
    stage_type: 'cover',
    content: '根据已定稿的小说信息、人物圣经、梗概、分卷结构和章节施工图返回唯一 CoverBrief，只含 concept、image_prompt、palette、negative_constraints；不得返回资产 ID、URL 或生成状态。',
    variables: [...promptMaterialKeys.cover],
  },
];
