import type { ProviderProfile, ProviderTemplate, WorkflowDefinition } from '../contracts';

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
      return {
        ...node,
        model_settings: ownsStageModel ? { ...node.model_settings, model: next.default_model } : node.model_settings,
      };
    }),
  };
}

export function withoutStageProviderExceptions(workflow: WorkflowDefinition): WorkflowDefinition {
  const defaultText = workflow.provider_profiles.find((provider) => provider.kind === 'openai-compatible' && provider.is_global_default);
  const defaultImage = workflow.provider_profiles.find((provider) => provider.kind === 'openai-compatible-image' && provider.is_global_default);
  if (!defaultText) return workflow;
  return {
    ...workflow,
    nodes: workflow.nodes.map((stage) => ({
      ...stage,
      provider_profile_id: defaultText.id,
      image_provider_profile_id: stage.type === 'cover' && defaultImage ? defaultImage.id : stage.image_provider_profile_id,
      model_settings: { ...stage.model_settings, model: defaultText.default_model },
    })),
  };
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
    model_supported_parameters: {},
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
    model_supported_parameters: {},
    estimated_cost_per_output_usd: null,
    is_global_default: false,
    enabled: true,
  };
}
