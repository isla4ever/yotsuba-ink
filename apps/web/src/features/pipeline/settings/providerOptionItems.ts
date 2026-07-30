import type { ProviderProfile, ProviderTemplate } from '../contracts';
import { modelNameForUi, providerNameForUi } from '../lib/display';
import type { OptionFieldItem } from './fields/optionFieldModel';

const integrationTierLabels: Record<ProviderTemplate['integration_tier'], string> = {
  official: '官方直连',
  compatibility: '官方兼容层',
  gateway: '聚合或自建网关',
  custom: '自定义兼容接口',
};

const integrationTierOrder: Record<ProviderTemplate['integration_tier'], number> = {
  official: 0,
  compatibility: 1,
  gateway: 2,
  custom: 3,
};

export function integrationTierLabel(tier: ProviderTemplate['integration_tier']) {
  return integrationTierLabels[tier];
}

export function providerTemplateOptionItems(templates: ProviderTemplate[]): OptionFieldItem[] {
  return templates
    .map((template, sourceIndex) => ({ template, sourceIndex }))
    .sort((left, right) => integrationTierOrder[left.template.integration_tier] - integrationTierOrder[right.template.integration_tier]
      || left.sourceIndex - right.sourceIndex)
    .map(({ template }) => ({
    value: template.id,
    label: template.label,
    description: template.description,
    group: integrationTierLabel(template.integration_tier),
    meta: template.kind === 'openai-compatible-image' ? '图片' : '文本',
    }));
}

export function providerOptionItems(providers: ProviderProfile[]): OptionFieldItem[] {
  return providers.map((provider) => ({
    value: provider.id,
    label: providerNameForUi(provider),
    meta: modelNameForUi(provider.default_model),
    disabled: !provider.enabled,
  }));
}
