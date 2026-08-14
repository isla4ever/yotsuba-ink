import type { PromptTemplate } from '../contracts';

type PromptStageId = Exclude<PromptTemplate['stage_type'], 'export'>;

export const promptMaterialKeys: Record<PromptStageId, string[]> = {
  brief: ['project_brief', 'length_envelope', 'source_pack', 'revision_request'],
  spine: ['story_brief', 'source_observations', 'scale_plan', 'revision_request'],
  cast: ['story_brief', 'story_spine', 'role_demand_proposals', 'subject_refs', 'scale_plan', 'revision_request'],
  volumes: ['story_brief', 'story_spine', 'character_bible_refs', 'volume_boundaries', 'scale_plan', 'closure_policy', 'revision_request'],
  detail: ['volume_contract', 'volume_spine_turns', 'scale_projection', 'selected_dossiers', 'active_thread_refs', 'previous_segment_handoff', 'revision_request'],
  text: ['chapter_context_manifest'],
  cover: ['accepted_story_metadata', 'visual_decisions', 'revision_request'],
};

export const defaultPromptTemplates: PromptTemplate[] = [
  {
    id: 'prompt-brief',
    name: '创作立项 Prompt',
    stage_type: 'brief',
    content: `你是类型小说立项编辑。只返回一个 JSON object，字段严格为 title、premise、promise、world_rules、theme、ending_promise、voice、length_envelope。不得返回人物、卷、章节、解释文本或额外字段。`,
    variables: [...promptMaterialKeys.brief],
  },
  {
    id: 'prompt-spine',
    name: '故事脊柱 Prompt',
    stage_type: 'spine',
    content: `你是故事因果编辑。只返回 StorySpineDraftArtifact JSON：turns、ending、open_questions、progress_types。turns 每项只有 cause、change，不返回 id，运行时按顺序绑定；不得写人物档案、卷号、章号、场景或额外字段。`,
    variables: [...promptMaterialKeys.spine],
  },
  {
    id: 'prompt-cast',
    name: '人物圣经 Prompt',
    stage_type: 'cast',
    content: `你是人物编排编辑。只返回 CharacterDossierBatch JSON：subjects 每项只含 name、kind、function、drive、change、debut、limits、demand_refs，不返回 subject id 或 relations。运行时按顺序绑定 subject_refs，关系由独立窄调用生成。不得新增未分配主体或额外字段。`,
    variables: [...promptMaterialKeys.cast],
  },
  {
    id: 'prompt-volumes',
    name: '分卷架构 Prompt',
    stage_type: 'volumes',
    content: `你是分卷故事架构师。只返回 VolumeArchitectureDraftArtifact JSON。每卷只含 promise、conflict、climax、closure、cast_ids、thread_ids、length_hint，不返回 volume id 或 turn_refs，运行时与已校验边界绑定；每卷必须形成完整局部故事，不得返回固定章窗、人物行为脚本或额外字段。`,
    variables: [...promptMaterialKeys.volumes],
  },
  {
    id: 'prompt-detail',
    name: '章节施工图 Prompt',
    stage_type: 'detail',
    content: `你是章节施工图编辑。当前输入只包含一个 volume_contract、对应的 volume_spine_turns、scale_projection、selected_dossiers、active_thread_refs 和可选 previous_segment_handoff。只返回这个叙事单元的 DetailSegmentArtifact JSON，且必须完整包含唯一顶层键 chapters，不得省略合同字段或返回额外键。每章只含 purpose、pov、cast_ids、scenes、handoff，不返回 chapter ref 或 volume ref，运行时按调用顺序绑定；cast_ids 是本章实际出场主体的去重引用，必须包含 pov 且只能引用 selected_dossiers，不在 scene 重复人物字段；每个 scene 只含 place、objective、conflict、turn、result。只消费本段给出的因果 turns；scale_projection 是软目标与合理范围，先保证本卷承诺、高潮和闭合，不得为命中数字压缩高潮或注水。不得创建新人物、复制上游散文或写 Wiki/Canon。`,
    variables: [...promptMaterialKeys.detail],
  },
  {
    id: 'prompt-text',
    name: '正文 Prompt',
    stage_type: 'text',
    content: `你是成熟的类型小说作者。根据唯一 ChapterContextManifest 只输出当前章节正文纯文本，不包 JSON、Markdown fence、标题元数据或解释。不得返回由 LangGraph 运行时持有的 version_id。不得检索未提供资料，不得新增未注册主体，不做 Wiki/Canon 写回。`,
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
