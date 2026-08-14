import type { ProviderProfile, WorkflowDefinition } from '../contracts';

/**
 * Stage-to-service binding repair, mirroring the backend rule applied when a
 * book is created. A book copied from a template can name a service the reader
 * never connected; rebinding every unusable stage to the connected default is
 * the only remedy that does not require walking eight stage inspectors.
 */
export function providerIsConnected(provider: ProviderProfile | undefined) {
  if (!provider || !provider.enabled) return false;
  if (!provider.base_url.trim() || !provider.default_model.trim()) return false;
  return Boolean(provider.has_saved_secret || provider.has_env_secret);
}

export function connectedProvider(profiles: ProviderProfile[], kind: ProviderProfile['kind']) {
  const usable = profiles.filter((provider) => provider.kind === kind && providerIsConnected(provider));
  return usable.find((provider) => provider.is_global_default) ?? usable[0];
}

export function stagesNeedingRebind(workflow: WorkflowDefinition) {
  const byId = new Map(workflow.provider_profiles.map((provider) => [provider.id, provider]));
  return workflow.nodes.filter((stage) => !providerIsConnected(byId.get(stage.provider_profile_id)));
}

export function withStagesBoundToConnectedProviders(workflow: WorkflowDefinition) {
  const byId = new Map(workflow.provider_profiles.map((provider) => [provider.id, provider]));
  const text = connectedProvider(workflow.provider_profiles, 'openai-compatible');
  const image = connectedProvider(workflow.provider_profiles, 'openai-compatible-image');
  if (!text && !image) return workflow;
  return {
    ...workflow,
    nodes: workflow.nodes.map((stage) => {
      let next = stage;
      if (text && !providerIsConnected(byId.get(stage.provider_profile_id))) {
        next = {
          ...next,
          provider_profile_id: text.id,
          model_settings: { ...next.model_settings, model: text.default_model },
        };
      }
      if (image && stage.type === 'cover' && !providerIsConnected(byId.get(stage.image_provider_profile_id ?? ''))) {
        next = { ...next, image_provider_profile_id: image.id };
      }
      return next;
    }),
  };
}
