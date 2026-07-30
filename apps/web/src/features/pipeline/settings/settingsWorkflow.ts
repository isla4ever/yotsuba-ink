import type { FallbackTarget, ProviderProfile, ProviderTemplate, WorkflowDefinition } from '../contracts';

export type GlobalFallbackChannel = 'text' | 'image';

export function withGlobalDefaultProvider(workflow: WorkflowDefinition, providerId: string, kind: ProviderProfile['kind'] = 'openai-compatible'): WorkflowDefinition {
  return {
    ...workflow,
    provider_profiles: workflow.provider_profiles.map((provider) => ({
      ...provider,
      is_global_default: provider.kind === kind ? provider.id === providerId : provider.is_global_default,
    })),
  };
}

export function withProviderProfile(workflow: WorkflowDefinition, provider: ProviderProfile): WorkflowDefinition {
  return { ...workflow, provider_profiles: [...workflow.provider_profiles, provider] };
}

export function withoutProviderProfile(workflow: WorkflowDefinition, providerId: string): WorkflowDefinition {
  return {
    ...workflow,
    provider_profiles: workflow.provider_profiles.filter((provider) => provider.id !== providerId),
  };
}

export function providerDeletionBlockReason(workflow: WorkflowDefinition, providerId: string): string {
  const provider = workflow.provider_profiles.find((item) => item.id === providerId);
  if (provider?.is_global_default) return '请先更换该类型的全局默认接口';
  const assigned = workflow.nodes.find((node) => (
    node.provider_profile_id === providerId
    || node.image_provider_profile_id === providerId
    || node.variant_policy.judge_provider_profile_id === providerId
    || (node.fallback_targets ?? []).some((target) => target.provider_profile_id === providerId)
    || (node.image_fallback_targets ?? []).some((target) => target.provider_profile_id === providerId)
  ));
  return assigned ? `请先更换“${assigned.label}”阶段中的接口分配` : '';
}

export function withProviderModelOption(workflow: WorkflowDefinition, providerId: string, model: string): WorkflowDefinition {
  return {
    ...workflow,
    provider_profiles: workflow.provider_profiles.map((provider) => provider.id === providerId
      ? { ...provider, model_options: Array.from(new Set([...(provider.model_options ?? []), model])) }
      : provider),
  };
}

export function replaceProviderProfile(workflow: WorkflowDefinition, next: ProviderProfile): WorkflowDefinition {
  const previous = workflow.provider_profiles.find((provider) => provider.id === next.id);
  if (!previous) return withProviderProfile(workflow, next);
  return {
    ...workflow,
    provider_profiles: workflow.provider_profiles.map((provider) => provider.id === next.id ? next : provider),
    nodes: workflow.nodes.map((node) => {
      const ownsStageModel = node.provider_profile_id === next.id
        && (!node.model_settings.model || node.model_settings.model === previous.default_model);
      const ownsJudgeModel = node.variant_policy.judge_model === previous.default_model
        && (node.variant_policy.judge_provider_profile_id === next.id
          || (node.variant_policy.judge_provider_profile_id === 'inherit' && previous.is_global_default));
      return {
        ...node,
        model_settings: ownsStageModel ? { ...node.model_settings, model: next.default_model } : node.model_settings,
        variant_policy: ownsJudgeModel ? { ...node.variant_policy, judge_model: next.default_model } : node.variant_policy,
        fallback_targets: updateFallbackModels(node.fallback_targets, next, previous.default_model),
        image_fallback_targets: updateFallbackModels(node.image_fallback_targets, next, previous.default_model),
      };
    }),
  };
}

export function withoutStageProviderExceptions(workflow: WorkflowDefinition): WorkflowDefinition {
  const defaultText = workflow.provider_profiles.find((provider) => provider.kind === 'openai-compatible' && provider.is_global_default)
    ?? workflow.provider_profiles.find((provider) => provider.kind === 'openai-compatible');
  const defaultImage = workflow.provider_profiles.find((provider) => provider.kind === 'openai-compatible-image' && provider.is_global_default)
    ?? workflow.provider_profiles.find((provider) => provider.kind === 'openai-compatible-image');
  if (!defaultText) return workflow;
  return {
    ...workflow,
    nodes: workflow.nodes.map((stage) => ({
      ...stage,
      provider_profile_id: defaultText.id,
      image_provider_profile_id: stage.type === 'cover_image' && defaultImage ? defaultImage.id : stage.image_provider_profile_id,
      model_settings: { ...stage.model_settings, model: defaultText.default_model },
      variant_policy: {
        ...stage.variant_policy,
        judge_provider_profile_id: 'inherit',
        judge_model: defaultText.default_model,
      },
    })),
  };
}

export function globalFallbackTargets(
  workflow: WorkflowDefinition,
  channel: GlobalFallbackChannel,
): FallbackTarget[] {
  const stages = workflow.nodes.filter((stage) => (
    channel === 'image' ? stage.type === 'cover_image' : Boolean(stage.provider_profile_id)
  ));
  const targetKey = channel === 'image' ? 'image_fallback_targets' : 'fallback_targets';
  const firstConfigured = stages.find((stage) => (stage[targetKey] ?? []).some((target) => target.enabled));
  return [...(firstConfigured?.[targetKey] ?? [])]
    .filter((target) => target.enabled)
    .sort((left, right) => left.priority - right.priority);
}

export function withGlobalFallbackProviders(
  workflow: WorkflowDefinition,
  channel: GlobalFallbackChannel,
  providerIds: string[],
): WorkflowDefinition {
  const kind = channel === 'image' ? 'openai-compatible-image' : 'openai-compatible';
  const available = new Map(workflow.provider_profiles
    .filter((provider) => provider.enabled && provider.kind === kind)
    .map((provider) => [provider.id, provider]));
  const uniqueProviderIds = Array.from(new Set(providerIds)).filter((providerId) => available.has(providerId)).slice(0, 3);

  return {
    ...workflow,
    nodes: workflow.nodes.map((stage) => {
      if (channel === 'image' && stage.type !== 'cover_image') return stage;
      const primaryId = channel === 'image' ? stage.image_provider_profile_id : stage.provider_profile_id;
      const targets = uniqueProviderIds
        .filter((providerId) => providerId !== primaryId)
        .map((providerId, index) => ({
          provider_profile_id: providerId,
          model: available.get(providerId)?.default_model ?? '',
          enabled: true,
          priority: index + 1,
        }));
      return channel === 'image'
        ? { ...stage, image_fallback_targets: targets }
        : { ...stage, fallback_targets: targets };
    }),
  };
}

function updateFallbackModels(
  targets: WorkflowDefinition['nodes'][number]['fallback_targets'],
  provider: ProviderProfile,
  previousDefaultModel: string,
) {
  return targets?.map((target) => target.provider_profile_id === provider.id && target.model === previousDefaultModel
    ? { ...target, model: provider.default_model }
    : target);
}

export function applyProviderTemplate(provider: ProviderProfile, template: ProviderTemplate): ProviderProfile {
  if (provider.kind !== template.kind) return provider;
  const modelOptions = template.model_options.length > 0
    ? [...template.model_options]
    : [...(provider.model_options ?? [])];
  return {
    ...provider,
    name: template.label,
    template_id: template.id,
    base_url: template.base_url,
    api_key_env: template.api_key_env,
    default_model: template.default_model,
    model_options: modelOptions,
    estimated_cost_per_output_usd: template.id === provider.template_id
      ? provider.estimated_cost_per_output_usd
      : null,
  };
}

export function providerProfileFromTemplate(
  template: ProviderTemplate,
  existingIds: string[],
): ProviderProfile {
  const rootId = `provider-${template.id}`;
  let id = rootId;
  let suffix = 2;
  while (existingIds.includes(id)) {
    id = `${rootId}-${suffix}`;
    suffix += 1;
  }
  return {
    id,
    name: template.label,
    kind: template.kind,
    template_id: template.id,
    base_url: template.base_url,
    api_key_env: template.api_key_env,
    default_model: template.default_model,
    model_options: [...template.model_options],
    estimated_cost_per_output_usd: null,
    is_global_default: false,
    enabled: true,
  };
}
