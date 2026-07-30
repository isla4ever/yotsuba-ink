import type { ProviderProfile, WorkflowStage } from '../contracts';

export function stageHasProviderException(stage: WorkflowStage, providers: ProviderProfile[]) {
  const defaultText = defaultProvider(providers, 'openai-compatible');
  const defaultImage = defaultProvider(providers, 'openai-compatible-image');
  const assigned = providers.find((provider) => provider.id === stage.provider_profile_id);
  const textException = Boolean(
    !defaultText
    || stage.provider_profile_id !== defaultText.id
    || stage.model_settings.model !== (assigned?.default_model ?? defaultText.default_model),
  );
  const imageException = stage.type === 'cover_image' && Boolean(
    !defaultImage || stage.image_provider_profile_id !== defaultImage.id,
  );
  const judgeException = stage.variant_policy.judge_provider_profile_id !== 'inherit';
  return textException || imageException || judgeException;
}

export function resetStageProviderException(stage: WorkflowStage, providers: ProviderProfile[]): WorkflowStage {
  const defaultText = defaultProvider(providers, 'openai-compatible');
  const defaultImage = defaultProvider(providers, 'openai-compatible-image');
  if (!defaultText) return stage;
  return {
    ...stage,
    provider_profile_id: defaultText.id,
    image_provider_profile_id: stage.type === 'cover_image' && defaultImage ? defaultImage.id : stage.image_provider_profile_id,
    model_settings: { ...stage.model_settings, model: defaultText.default_model },
    variant_policy: {
      ...stage.variant_policy,
      judge_provider_profile_id: 'inherit',
      judge_model: defaultText.default_model,
    },
  };
}

export function stageProviderSummary(stage: WorkflowStage, providers: ProviderProfile[]) {
  const provider = providers.find((item) => item.id === stage.provider_profile_id);
  return `${provider?.name || '未设置文本服务'} · ${stage.model_settings.model || '模型未设置'}`;
}

function defaultProvider(providers: ProviderProfile[], kind: ProviderProfile['kind']) {
  const candidates = providers.filter((provider) => provider.kind === kind);
  return candidates.find((provider) => provider.is_global_default) ?? candidates[0];
}
