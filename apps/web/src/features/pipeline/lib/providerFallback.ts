import type { FallbackTarget, ProviderProfile, WorkflowStage } from '../contracts';

export type FallbackChannel = 'text' | 'image';

export function fallbackTargets(stage: WorkflowStage, channel: FallbackChannel): FallbackTarget[] {
  const targets = channel === 'image' ? stage.image_fallback_targets : stage.fallback_targets;
  return [...(targets ?? [])].sort((left, right) => left.priority - right.priority);
}

export function addFallbackTarget(
  stage: WorkflowStage,
  providers: ProviderProfile[],
  channel: FallbackChannel,
): WorkflowStage {
  const targets = fallbackTargets(stage, channel);
  if (targets.length >= 3) return stage;
  const primaryId = channel === 'image' ? stage.image_provider_profile_id : stage.provider_profile_id;
  const used = new Set(targets.map((target) => target.provider_profile_id));
  const kind = channel === 'image' ? 'openai-compatible-image' : 'openai-compatible';
  const provider = providers.find((item) => item.enabled && item.kind === kind && item.id !== primaryId && !used.has(item.id));
  if (!provider) return stage;
  return withTargets(stage, channel, [
    ...targets,
    { provider_profile_id: provider.id, model: provider.default_model, enabled: true, priority: targets.length + 1 },
  ]);
}

export function updateFallbackTarget(
  stage: WorkflowStage,
  providers: ProviderProfile[],
  channel: FallbackChannel,
  priority: number,
  update: Partial<FallbackTarget>,
): WorkflowStage {
  const targets = fallbackTargets(stage, channel).map((target) => {
    if (target.priority !== priority) return target;
    const next = { ...target, ...update };
    if (update.provider_profile_id && update.provider_profile_id !== target.provider_profile_id) {
      const provider = providers.find((item) => item.id === update.provider_profile_id);
      next.model = provider?.default_model ?? next.model;
    }
    return next;
  });
  return withTargets(stage, channel, targets);
}

export function removeFallbackTarget(stage: WorkflowStage, channel: FallbackChannel, priority: number): WorkflowStage {
  return withTargets(stage, channel, fallbackTargets(stage, channel).filter((target) => target.priority !== priority));
}

export function moveFallbackTarget(
  stage: WorkflowStage,
  channel: FallbackChannel,
  priority: number,
  direction: -1 | 1,
): WorkflowStage {
  const targets = fallbackTargets(stage, channel);
  const index = targets.findIndex((target) => target.priority === priority);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= targets.length) return stage;
  [targets[index], targets[nextIndex]] = [targets[nextIndex], targets[index]];
  return withTargets(stage, channel, targets);
}

export function removePrimaryFromFallbacks(stage: WorkflowStage, channel: FallbackChannel, providerId: string): WorkflowStage {
  return withTargets(stage, channel, fallbackTargets(stage, channel).filter((target) => target.provider_profile_id !== providerId));
}

function withTargets(stage: WorkflowStage, channel: FallbackChannel, targets: FallbackTarget[]): WorkflowStage {
  const normalized = targets.map((target, index) => ({ ...target, priority: index + 1 }));
  return channel === 'image'
    ? { ...stage, image_fallback_targets: normalized }
    : { ...stage, fallback_targets: normalized };
}
