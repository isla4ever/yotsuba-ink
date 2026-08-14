import type { ProviderProfile, WorkflowDefinition, WorkflowStage } from '../contracts';
import { defaultPromptTemplates } from './defaultPromptTemplates';

export const providers: ProviderProfile[] = [
  { id: 'openai-compatible', name: '文本接口', kind: 'openai-compatible', template_id: 'openai-compatible-text', base_url: '', api_key_env: 'NOVEL_LLM_API_KEY', default_model: 'gpt-4.1-mini', model_options: ['gpt-4.1-mini'], is_global_default: true, enabled: true },
  { id: 'openai-compatible-image', name: '图片接口', kind: 'openai-compatible-image', template_id: 'openai-compatible-image', base_url: '', api_key_env: 'NOVEL_IMAGE_API_KEY', default_model: 'gpt-image-2', model_options: ['gpt-image-2'], is_global_default: true, enabled: true },
];

export const prompts = defaultPromptTemplates;

const baseModel = { model: 'gpt-4.1-mini', temperature: 0.7, max_tokens: 2600, top_p: 0.95, timeout_seconds: 120 };

const generationBudgets = {
  brief: { max_tokens: 4600, description: '创作立项冻结承诺、世界规则、主题、结局方向、叙事声音与篇幅包络。' },
  spine: { max_tokens: 5000, description: '输出精简的因果 turns、结局和开放问题；不提前分章或编排人物行为。' },
  cast: { max_tokens: 7500, description: '人物档案按 role demand 分组生成，关系由独立窄调用建立。' },
  volumes: { max_tokens: 6000, description: '按自然卷界输出完整故事卷合同；卷数和章数不按固定模板填充。' },
  detail: { max_tokens: 6000, description: '按 Spine 因果边界和输出容量拆为叙事段，每章只规划必要场景与交接。' },
  text: { max_tokens: 6000, description: '单章纯文本输出，篇幅只服从冻结软目标与当前施工图。' },
  cover: { max_tokens: 2200, description: '封面 brief/prompt 与视觉候选。' },
};

export const stages: WorkflowStage[] = [
  {
    id: 'brief',
    type: 'brief',
    label: '创作立项定稿',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.brief.max_tokens },
    prompt_template_id: 'prompt-brief',
    input_schema: [
      { key: 'genre', label: '题材', type: 'select', required: true, default: '悬疑', options: ['悬疑', '玄幻', '都市', '科幻', '言情', '历史', '现实', '轻小说'] },
      { key: 'narrative_profile', label: '叙事角色', type: 'select', required: true, default: '故事建筑师', options: ['故事建筑师', '现场观察者', '心理戏剧家', '悬念导演', '群像编年者', '意象织造者'], help: '选择贯穿全书的观察与表达策略；角色 Prompt 只读。' },
      { key: 'word_target_soft', label: '软字数目标', type: 'number', required: false, default: 100000, hint: '仅作为节奏建议，不会自动删改正文。' },
      { key: 'chapter_target_soft', label: '软章数目标', type: 'number', required: false, default: null, hint: '仅作为规划建议，卷界和章节数量由剧情闭合决定。' },
      { key: 'volume_target_override', label: '自定义卷数', type: 'number', required: false, default: null, hint: '仅精工模式生效；留空沿用系统建议区间。' },
      { key: 'turn_target_override', label: '自定义脊柱转折数', type: 'number', required: false, default: null, hint: '仅精工模式生效；留空沿用系统建议区间。' },
      { key: 'cast_demand_override', label: '自定义人物数量', type: 'number', required: false, default: null, hint: '仅精工模式生效；留空沿用系统建议区间。' },
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
    generation_budget: generationBudgets.brief,
  },
  {
    id: 'spine',
    type: 'spine',
    label: '故事脊柱',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.spine.max_tokens },
    prompt_template_id: 'prompt-spine',
    input_schema: [
      { key: 'structure', label: '结构偏好', type: 'select', default: '自适应因果链', options: ['自适应因果链', '悬疑递进', '群像交织'] },
      { key: 'ending_direction', label: '结局方向', type: 'text', default: '真相公开但保留余味' },
    ],
    generation_budget: generationBudgets.spine,
  },
  {
    id: 'cast',
    type: 'cast',
    label: '人物圣经',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.cast.max_tokens },
    prompt_template_id: 'prompt-cast',
    input_schema: [],
    generation_budget: generationBudgets.cast,
  },
  {
    id: 'volumes',
    type: 'volumes',
    label: '分卷架构',
    provider_profile_id: 'openai-compatible',
    model_settings: { ...baseModel, max_tokens: generationBudgets.volumes.max_tokens },
    prompt_template_id: 'prompt-volumes',
    input_schema: [
      { key: 'conflict_density', label: '冲突密度', type: 'select', default: '中高', options: ['平缓', '中等', '中高', '高压'] },
    ],
    generation_budget: generationBudgets.volumes,
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
  architecture_version: 'phase27-vnext',
  id: 'default-novel-workflow',
  name: '长篇小说生产线工作流',
  version: '27.1.0-langgraph-native',
  global_inputs: [
    { key: 'title', label: '项目标题', type: 'text', required: true, default: '雾港旧声' },
  ],
  provider_profiles: providers,
  prompt_templates: prompts,
  quality_mode: 'balanced',
  canvas_layout: {
    nodes: {
      brief: { x: 20, y: 168 },
      spine: { x: 214, y: 168 },
      cast: { x: 408, y: 168 },
      volumes: { x: 602, y: 168 },
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
    { id: 'e-brief-spine', source: 'brief', target: 'spine' },
    { id: 'e-spine-cast', source: 'spine', target: 'cast' },
    { id: 'e-cast-volumes', source: 'cast', target: 'volumes' },
    { id: 'e-volumes-detail', source: 'volumes', target: 'detail' },
    { id: 'e-detail-text', source: 'detail', target: 'text' },
    { id: 'e-detail-cover', source: 'detail', target: 'cover' },
    { id: 'e-text-export', source: 'text', target: 'export' },
    { id: 'e-cover-export', source: 'cover', target: 'export' },
  ],
};

export const templates = ['全自动长篇小说生成', '短篇投稿生成', '只生成大纲', '批量选题/推荐', '正文续写 + Wiki 约束'];
