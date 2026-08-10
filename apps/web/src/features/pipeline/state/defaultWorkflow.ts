import type { ProviderProfile, WorkflowDefinition, WorkflowStage } from '../contracts';
import { defaultPromptTemplates } from './defaultPromptTemplates';

export const providers: ProviderProfile[] = [
  { id: 'openai-compatible', name: '文本接口', kind: 'openai-compatible', template_id: 'openai-compatible-text', base_url: '', api_key_env: 'NOVEL_LLM_API_KEY', default_model: 'gpt-4.1-mini', model_options: ['gpt-4.1-mini'], is_global_default: true, enabled: true },
  { id: 'openai-compatible-image', name: '图片接口', kind: 'openai-compatible-image', template_id: 'openai-compatible-image', base_url: '', api_key_env: 'NOVEL_IMAGE_API_KEY', default_model: 'gpt-image-2', model_options: ['gpt-image-2'], is_global_default: true, enabled: true },
];

export const prompts = defaultPromptTemplates;

const baseModel = { model: 'gpt-4.1-mini', temperature: 0.7, max_tokens: 2600, top_p: 0.95, timeout_seconds: 120 };

const generationBudgets = {
  info: { target_chars: 2200, min_chars: 1400, max_chars: 3200, max_tokens: 4600, description: '创作立项 Story Brief：冻结题材承诺、世界规则、主题问题、结局承诺与叙事声音。' },
  characters: { target_chars: 1800, min_chars: 1000, max_chars: 3200, max_tokens: 4200, description: '人物圣经：冻结角色职责、关系、弧线与首次出现窗口。' },
  summary: { target_chars: 1200, min_chars: 1200, max_chars: 2800, max_tokens: 3600, description: '完整全书梗概：覆盖完整故事、人物变化与结局承诺。' },
  outline: { target_chars: 1400, min_chars: 1400, max_chars: 3600, max_tokens: 4200, description: '分卷 beat board：字段完整，不从自由文本二次拆节拍。' },
  detail: { target_chars: 2400, min_chars: 1800, max_chars: 5600, max_tokens: 6000, description: '三章施工细纲：默认每章一个主场景，仅在紧密不可拆的转场中使用第二场，并把未完成动作交给下一章。' },
  text: { target_chars: 1700, min_chars: 1400, max_chars: 2200, max_tokens: 3600, description: '单章正文：建议在 1700 字符附近自然收束，通常落在 1400-2200 字符。' },
  cover: { target_chars: 500, min_chars: 500, max_chars: 1400, max_tokens: 2200, description: '封面 brief/prompt 与视觉候选。' },
};

export const stages: WorkflowStage[] = [
  {
    id: 'info',
    type: 'info',
    label: '创作立项定稿',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.info.max_tokens },
    prompt_template_id: 'prompt-info',
    input_schema: [
      { key: 'genre', label: '题材', type: 'select', required: true, default: '悬疑', options: ['悬疑', '玄幻', '都市', '科幻', '言情', '历史', '现实', '轻小说'] },
      { key: 'narrative_profile', label: '叙事角色', type: 'select', required: true, default: '故事建筑师', options: ['故事建筑师', '现场观察者', '心理戏剧家', '悬念导演', '群像编年者', '意象织造者'], help: '选择贯穿全书的观察与表达策略；角色 Prompt 只读。' },
      { key: 'book_scale_target_mode', label: '成书目标', type: 'select', required: true, default: 'total_chars', options: ['total_chars', 'total_chapters'], hint: '总字数与总章数二选一，系统自动推导卷数、章数和各阶段预算。' },
      { key: 'book_scale_target_value', label: '目标值', type: 'number', required: true, default: 100000, hint: '总字数按中文可见字符计算；选择总章数时填写计划章节数。' },
      { key: 'audience', label: '目标读者', type: 'text', required: true, default: '偏好强情节、悬念推进、人物关系清晰的网文读者' },
      { key: 'core_concept', label: '核心创意/冲突', type: 'textarea', required: true, default: '旧港多年前的记忆实验留下旧案回声，主角追查真相时发现自己最可信的记忆也被改写。', hint: '立项只需要一个能撑起全书的核心冲突；世界规则在本阶段形成，人物职责与关系在下一阶段冻结。' },
      { key: 'keywords', label: '关键词', type: 'tags', required: true, default: ['旧港', '记忆实验', '群像', '旧案'] },
      { key: 'taboos', label: '禁忌/不要出现', type: 'textarea', required: true, default: '避免无动机黑化、机械降神、纯设定堆砌、套路化系统开局和无关恋爱线抢主线。' },
      { key: 'reference_mode', label: '参考源模式', type: 'select', required: true, default: 'smart_search', options: ['smart_search', 'url', 'knowledge_base'] },
      { key: 'reference_keywords', label: '参考关键词', type: 'tags', default: ['长篇悬疑', '记忆', '群像', '伏笔'] },
      { key: 'reference_query_intent', label: '参考检索意图', type: 'textarea', default: '检索旧港、记忆实验、群像悬疑结构的参考材料；只提炼结构、节奏、题材约束，不返回可照搬桥段。' },
      { key: 'reference_urls', label: '指定链接', type: 'tags', default: [] },
      { key: 'knowledge_base_doc_ids', label: '知识库文档', type: 'tags', default: [] },
      { key: 'enable_web_search', label: '智能搜索使用联网', type: 'boolean', default: true },
      { key: 'reference_summary', label: '参考资料摘要', type: 'textarea', default: '' },
    ],
    generation_budget: generationBudgets.info,
  },
  {
    id: 'characters',
    type: 'characters',
    label: '人物圣经',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.characters.max_tokens },
    prompt_template_id: 'prompt-characters',
    input_schema: [],
    generation_budget: generationBudgets.characters,
  },
  {
    id: 'summary',
    type: 'summary',
    label: '全书梗概',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.summary.max_tokens },
    prompt_template_id: 'prompt-summary',
    input_schema: [
      { key: 'structure', label: '结构偏好', type: 'select', default: '起承转合', options: ['起承转合', '三幕式', '悬疑递进', '群像交织'] },
      { key: 'ending_direction', label: '结局方向', type: 'text', default: '真相公开但保留余味' },
    ],
    generation_budget: generationBudgets.summary,
  },
  {
    id: 'outline',
    type: 'outline',
    label: '分卷大纲',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.outline.max_tokens },
    prompt_template_id: 'prompt-outline',
    input_schema: [
      { key: 'conflict_density', label: '冲突密度', type: 'select', default: '中高', options: ['平缓', '中等', '中高', '高压'] },
    ],
    generation_budget: generationBudgets.outline,
  },
  {
    id: 'detail',
    type: 'detail',
    label: '章节施工图',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.detail.max_tokens },
    prompt_template_id: 'prompt-detail',
    input_schema: [
      { key: 'must_include', label: '每章必须包含', type: 'tags', default: ['目标', '冲突', '伏笔', '章末钩子'] },
    ],
    generation_budget: generationBudgets.detail,
  },
  {
    id: 'text',
    type: 'text',
    label: '正文生成',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.text.max_tokens, temperature: 0.82 },
    prompt_template_id: 'prompt-text',
    input_schema: [
      { key: 'pov', label: '叙事视角', type: 'select', default: '第三人称有限视角', options: ['第一人称', '第三人称有限视角', '多视角'] },
    ],
    generation_budget: generationBudgets.text,
  },
  {
    id: 'cover',
    type: 'cover',
    label: 'AI 封面',
    provider_profile_id: 'openai-compatible',
    image_provider_profile_id: 'openai-compatible-image',
    model_settings: { ...baseModel, model: 'gpt-4.1-mini', max_tokens: generationBudgets.cover.max_tokens },
    prompt_template_id: 'prompt-cover',
    input_schema: [
      { key: 'cover_style', label: '封面风格', type: 'select', default: '电影感悬疑', options: ['电影感悬疑', '国风幻想', '赛博科幻', '青春现实'] },
      { key: 'image_size', label: '图片尺寸', type: 'select', default: '1024x1536', options: ['1024x1536'] },
      { key: 'candidate_count', label: '图片候选数', type: 'number', default: 3, help: '每个候选对应一次独立图片生成，范围 1-4。' },
      { key: 'image_quality', label: '图片质量', type: 'select', default: 'medium', options: ['low', 'medium', 'high'] },
    ],
    generation_budget: generationBudgets.cover,
  },
  {
    id: 'export',
    type: 'export',
    label: '导出产物',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel },
    prompt_template_id: '',
    input_schema: [
      { key: 'export_format', label: '导出格式', type: 'select', default: 'zip', options: ['zip', 'md', 'json'] },
      { key: 'author', label: '作者', type: 'text', default: '' },
      { key: 'version_note', label: '版本说明', type: 'text', default: '' },
    ],
  },
];

export const defaultWorkflow: WorkflowDefinition = {
  id: 'default-novel-workflow',
  name: '长篇小说生产线工作流',
  version: '26.1.0-langgraph-vnext',
  global_inputs: [
    { key: 'title', label: '项目标题', type: 'text', required: true, default: '雾港旧声' },
  ],
  provider_profiles: providers,
  prompt_templates: prompts,
  quality_mode: 'balanced',
  canvas_layout: {
    nodes: {
      info: { x: 20, y: 168 },
      characters: { x: 214, y: 168 },
      summary: { x: 408, y: 168 },
      outline: { x: 602, y: 168 },
      detail: { x: 796, y: 168 },
      text: { x: 990, y: 168 },
      cover: { x: 1184, y: 168 },
      export: { x: 1378, y: 168 },
      'wiki-layer': { x: 480, y: -96 },
      'quality-layer': { x: 900, y: 452 },
    },
    viewport: { x: 0, y: 0, zoom: 0.76 },
    crosscutting_visible: true,
    locked: false,
  },
  nodes: stages,
  edges: [
    { id: 'e-info-characters', source: 'info', target: 'characters' },
    { id: 'e-characters-summary', source: 'characters', target: 'summary' },
    { id: 'e-summary-outline', source: 'summary', target: 'outline' },
    { id: 'e-outline-detail', source: 'outline', target: 'detail' },
    { id: 'e-detail-text', source: 'detail', target: 'text' },
    { id: 'e-detail-cover', source: 'detail', target: 'cover' },
    { id: 'e-text-export', source: 'text', target: 'export' },
    { id: 'e-cover-export', source: 'cover', target: 'export' },
  ],
};

export const templates = ['全自动长篇小说生成', '短篇投稿生成', '只生成大纲', '批量选题/推荐', '正文续写 + Wiki 约束'];
