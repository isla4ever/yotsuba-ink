import type { ProviderProfile, WorkflowStage } from '../contracts';

const providerLabels: Record<string, string> = {};

const modelLabels: Record<string, string> = {};

const kindLabels: Record<ProviderProfile['kind'], string> = {
  'openai-compatible': 'OpenAI-compatible',
  'openai-compatible-image': 'OpenAI-compatible 图片',
};

export function providerNameForUi(provider?: Pick<ProviderProfile, 'id' | 'name'> | string) {
  if (!provider) return '未连接 AI 服务';
  if (typeof provider === 'string') return providerLabels[provider] ?? scrubMockText(provider);
  return providerLabels[provider.id] ?? scrubMockText(provider.name);
}

export function modelNameForUi(model?: string) {
  if (!model) return '未配置模型';
  return modelLabels[model] ?? scrubMockText(model);
}

export function providerKindForUi(kind?: ProviderProfile['kind'] | string) {
  if (!kind) return '未配置类型';
  return kindLabels[kind as ProviderProfile['kind']] ?? scrubMockText(kind);
}

export function runtimeTextForUi(value?: string) {
  return scrubMockText(value ?? '');
}

export function stageLabelForUi(stage: Pick<WorkflowStage, 'label' | 'type'>) {
  return stage.type === 'info_recommend' ? '小说信息推荐' : stage.label;
}

export function formatHistoryTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '时间未知';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatFileSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function scrubMockText(value: string) {
  return value;
}
