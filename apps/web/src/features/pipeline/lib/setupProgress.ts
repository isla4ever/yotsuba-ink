import type {
  InputField,
  SettingsSectionSummary,
  SetupDerivationInput,
  SetupIssue,
  SetupStep,
  SetupStepId,
  WorkflowDefinition,
  WorkflowStage,
} from '../contracts';
import { stageHasProviderException } from './stageProviderException';
import { creationModeTitle } from './terminology';

/** Book preparation stays focused on creative input; pipeline setup lives elsewhere. */
export const setupStepOrder: SetupStepId[] = ['story', 'review'];

/** Review-page card anchors: reference/mode issues focus these elements. */
export const reviewReferenceCardId = 'setup-review-references';
export const reviewCreationModeCardId = 'setup-review-creation-mode';

const storyFieldKeys = new Set([
  'genre',
  'word_target_soft',
  'audience',
  'core_concept',
  'keywords',
  'taboos',
]);

export function buildSetupSteps(input: SetupDerivationInput): SetupStep[] {
  const brief = briefStageOf(input.workflow);
  const storyIssues = storySetupIssues(brief);
  // References and creation mode live on the review page as default cards,
  // so their issues belong to the review step and anchor to the cards.
  const reviewOwnIssues = [
    ...referenceSetupIssues(brief, input.knowledgeDocuments),
    ...creationModeSetupIssues(input.workflow),
  ];
  const carriedBlocking = storyIssues.filter((issue) => issue.severity === 'blocking');
  const reviewIssues = [...reviewOwnIssues, ...carriedBlocking];
  const reviewBlockingCount = reviewIssues.filter((issue) => issue.severity === 'blocking').length;

  return [
    setupStep('story', '故事起点', storyIssues, storySummary(brief)),
    setupStep(
      'review',
      '确认启动',
      reviewIssues,
      reviewBlockingCount
        ? `${reviewBlockingCount} 项需要处理`
        : `${referenceSummary(brief, input.knowledgeDocuments)} · ${qualityModeLabel(input.workflow.quality_mode)}`,
    ),
  ];
}

export function firstBlockingSetupTarget(steps: SetupStep[]) {
  for (const step of steps) {
    const issue = step.issues.find((item) => item.severity === 'blocking');
    if (issue) return issue.target;
  }
  return null;
}

export function stageExceptionIds(workflow: WorkflowDefinition) {
  return workflow.nodes
    .filter((stage) => stageHasProviderException(stage, workflow.provider_profiles))
    .map((stage) => stage.id);
}

export function buildSettingsSections(input: SetupDerivationInput): SettingsSectionSummary[] {
  const brief = briefStageOf(input.workflow);
  const exceptionIds = stageExceptionIds(input.workflow);
  const sections: SettingsSectionSummary[] = [
    {
      id: 'story', title: '创作设定', status: statusFromIssues(storySetupIssues(brief)),
      summary: [storySummary(brief), valueFor(brief, 'audience') || '尚未填写目标读者'],
      action: { label: '修改', target: 'brief' },
    },
    {
      id: 'references', title: '参考与资料', status: statusFromIssues(referenceSetupIssues(brief, input.knowledgeDocuments)),
      summary: [referenceSummary(brief, input.knowledgeDocuments), referenceSourceSummary(brief)],
      action: { label: '管理', target: 'brief' },
    },
    {
      id: 'creation-mode', title: '创作模式', status: statusFromIssues(creationModeSetupIssues(input.workflow)),
      summary: [qualityModeLabel(input.workflow.quality_mode), qualityModeImpact(input.workflow.quality_mode)],
      action: { label: '修改', target: 'creation-mode' },
    },
    {
      id: 'ai-service', title: 'AI 服务与默认模型', status: statusFromIssues(aiServiceSetupIssues(input.readiness)),
      summary: [providerReadinessSummary(input.readiness), defaultProviderSummary(input.workflow.provider_profiles)],
      action: { label: '管理', target: 'ai-service' },
    },
  ];
  if (exceptionIds.length) sections.push({
      id: 'stage-exceptions', title: '高级阶段例外', status: exceptionIds.length ? 'warning' : 'informational',
      summary: [`${exceptionIds.length} 个阶段使用独立服务或模型`],
      action: { label: '查看', target: exceptionIds[0] },
    });
  return sections;
}

function briefStageOf(workflow: WorkflowDefinition) {
  return workflow.nodes.find((stage) => stage.type === 'brief');
}

function storySetupIssues(brief?: WorkflowStage): SetupIssue[] {
  if (!brief) return [blockingIssue('story_stage_missing', '找不到故事起点配置', 'story')];
  return brief.input_schema
    .filter((field) => field.required && storyFieldKeys.has(field.key) && !hasConfiguredValue(field))
    .map((field) => blockingIssue(`story_${field.key}_missing`, `请填写${field.label}`, 'story', `setup-story-${field.key}`));
}

function referenceSetupIssues(brief: WorkflowStage | undefined, documents: SetupDerivationInput['knowledgeDocuments']): SetupIssue[] {
  if (!brief) return [blockingIssue('reference_stage_missing', '找不到参考方式配置', 'review', reviewReferenceCardId)];
  const mode = valueFor(brief, 'reference_mode');
  if (!['smart_search', 'url', 'knowledge_base'].includes(mode)) {
    return [blockingIssue('reference_mode_missing', '请选择参考方式', 'review', reviewReferenceCardId)];
  }
  const selectedIds = arrayValueFor(brief, 'knowledge_base_doc_ids');
  const knownIds = new Set(documents.filter((document) => document.status === 'ready').map((document) => document.doc_id));
  const unavailable = selectedIds.filter((id) => !knownIds.has(id));
  if (unavailable.length) {
    return [blockingIssue('knowledge_document_unavailable', `${unavailable.length} 份已选资料当前不可用`, 'review', reviewReferenceCardId)];
  }
  if (mode === 'url' && !arrayValueFor(brief, 'reference_urls').length) {
    return [warningIssue('reference_url_empty', '未添加网页链接，将仅依据故事设定创作', 'review', reviewReferenceCardId)];
  }
  if (mode === 'knowledge_base' && !selectedIds.length) {
    return [warningIssue('knowledge_selection_empty', '未选择项目资料，将仅依据故事设定创作', 'review', reviewReferenceCardId)];
  }
  return [];
}

function aiServiceSetupIssues(readiness: SetupDerivationInput['readiness']): Array<Pick<SetupIssue, 'severity'>> {
  if (!readiness) return [{ severity: 'blocking' }];
  return readiness.checks
    .filter((check) => !check.ready)
    .map(() => ({ severity: 'blocking' as const }));
}

function creationModeSetupIssues(workflow: WorkflowDefinition): SetupIssue[] {
  return ['fast', 'balanced', 'deep'].includes(workflow.quality_mode)
    ? []
    : [blockingIssue('quality_mode_missing', '请选择创作模式', 'review', reviewCreationModeCardId)];
}

function setupStep(id: SetupStepId, label: string, issues: SetupIssue[], summary: string): SetupStep {
  const blocked = issues.some((issue) => issue.severity === 'blocking');
  return { id, label, issues, summary, status: blocked ? 'blocked' : 'complete' };
}

function blockingIssue(code: string, label: string, stepId: SetupStepId, fieldId?: string): SetupIssue {
  return { code, label, severity: 'blocking', target: { stepId, fieldId } };
}

function warningIssue(code: string, label: string, stepId: SetupStepId, fieldId?: string): SetupIssue {
  return { code, label, severity: 'warning', target: { stepId, fieldId } };
}

function hasConfiguredValue(field: InputField) {
  const value = field.default;
  if (field.type === 'boolean') return typeof value === 'boolean';
  if (field.type === 'number') return typeof value === 'number' && Number.isFinite(value);
  if (Array.isArray(value)) return value.some((item) => String(item).trim());
  return String(value ?? '').trim().length > 0;
}

function storySummary(brief?: WorkflowStage) {
  const genre = valueFor(brief, 'genre') || '题材未定';
  const words = Number(fieldFor(brief, 'word_target_soft')?.default);
  const scale = Number.isFinite(words) && words > 0
    ? `约 ${words.toLocaleString('zh-CN')} 字`
    : '体量未定';
  return `${genre} · ${scale}`;
}

export function referenceSummary(brief: WorkflowStage | undefined, documents: SetupDerivationInput['knowledgeDocuments']) {
  const selected = new Set(arrayValueFor(brief, 'knowledge_base_doc_ids'));
  const ready = documents.filter((document) => selected.has(document.doc_id) && document.status === 'ready').length;
  return `${referenceModeLabel(valueFor(brief, 'reference_mode'))} · ${ready} 份资料可用`;
}

function referenceSourceSummary(brief?: WorkflowStage) {
  const webEnabled = Boolean(fieldFor(brief, 'enable_web_search')?.default);
  const urlCount = arrayValueFor(brief, 'reference_urls').length;
  return `${webEnabled ? '联网参考已开启' : '仅使用本地内容'} · ${urlCount} 个指定链接`;
}

export function providerReadinessSummary(readiness: SetupDerivationInput['readiness']) {
  if (!readiness) return 'AI 服务状态待确认';
  const ready = readiness.checks.filter((check) => check.ready).length;
  return readiness.ok ? `${ready} 项服务检查通过` : `${readiness.checks.length - ready} 项服务需要处理`;
}

function defaultProviderSummary(providers: WorkflowDefinition['provider_profiles']) {
  const text = globalProvider(providers, 'openai-compatible');
  const image = globalProvider(providers, 'openai-compatible-image');
  return `${text?.name || '文本服务未设置'} · ${image?.name || '封面服务未设置'}`;
}

function globalProvider(providers: WorkflowDefinition['provider_profiles'], kind: WorkflowDefinition['provider_profiles'][number]['kind']) {
  const candidates = providers.filter((provider) => provider.kind === kind);
  return candidates.find((provider) => provider.is_global_default) ?? candidates[0];
}

function qualityModeLabel(mode: WorkflowDefinition['quality_mode']) {
  return creationModeTitle(mode);
}

function qualityModeImpact(mode: WorkflowDefinition['quality_mode']) {
  if (mode === 'fast') return '阶段与章节决策自动接受';
  if (mode === 'deep') return '逐阶段逐章确认 · 三路审稿必需';
  return '逐阶段逐章确认 · 文风审稿可选';
}

export function referenceModeLabel(mode: string) {
  if (mode === 'url') return '指定网页';
  if (mode === 'knowledge_base') return '项目资料';
  return '智能参考';
}

function statusFromIssues(issues: Array<Pick<SetupIssue, 'severity'>>): SettingsSectionSummary['status'] {
  if (issues.some((issue) => issue.severity === 'blocking')) return 'blocked';
  if (issues.length) return 'warning';
  return 'ready';
}

function fieldFor(stage: WorkflowStage | undefined, key: string) {
  return stage?.input_schema.find((field) => field.key === key);
}

function valueFor(stage: WorkflowStage | undefined, key: string) {
  return String(fieldFor(stage, key)?.default ?? '').trim();
}

function arrayValueFor(stage: WorkflowStage | undefined, key: string) {
  const value = fieldFor(stage, key)?.default;
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}
