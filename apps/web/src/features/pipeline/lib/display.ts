import type { ProviderProfile } from '../contracts';

const providerLabels: Record<string, string> = {
  'mock-text': '演示文本模型',
  'mock-image': '演示封面模型',
};

const modelLabels: Record<string, string> = {
  'mock-novel-model': '演示小说模型',
  'mock-novel-judge': '演示评审模型',
  'mock-cover': '演示封面模型',
};

const kindLabels: Record<ProviderProfile['kind'], string> = {
  mock: '本地演示通道',
  'image-mock': '本地封面演示通道',
  'openai-compatible': 'OpenAI-compatible',
};

export function providerNameForUi(provider?: Pick<ProviderProfile, 'id' | 'name'> | string) {
  if (!provider) return '未配置 Provider';
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

function scrubMockText(value: string) {
  return value
    .replace(/mock-novel-judge/gi, '演示评审模型')
    .replace(/mock-novel-model/gi, '演示小说模型')
    .replace(/mock-cover/gi, '演示封面模型')
    .replace(/mock-text/gi, '演示文本模型')
    .replace(/mock-image/gi, '演示封面模型')
    .replace(/Mock\/无需密钥/gi, '本地演示通道')
    .replace(/Mock/gi, '演示')
    .replace(/mock/gi, '演示');
}
