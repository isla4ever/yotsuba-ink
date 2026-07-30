import type { RunEvent, UsageSnapshot } from '../contracts';

/**
 * Phase 12 D1: the backend reports real usage via `stage_usage_updated`
 * (in-flight) and `stage_usage_finalized` (settlement). The legacy
 * `usage_snapshot_updated` name was never emitted, which left usage panels
 * showing zeros. Events arrive newest-first, so the first match per chapter
 * scope is the most recent (finalized wins over the update it follows).
 * Returns null when the run has not reported usage, so consumers can render
 * 「暂无」 instead of fake zeros.
 */
export function stageUsageFromEvents(events: RunEvent[], stageId: string): UsageSnapshot | null {
  const byScope = new Map<string, UsageSnapshot>();
  for (const event of events) {
    if (event.node_id !== stageId || !event.usage) continue;
    if (event.type !== 'stage_usage_finalized' && event.type !== 'stage_usage_updated') continue;
    const scope = String(event.chapter ?? '');
    if (!byScope.has(scope)) byScope.set(scope, event.usage);
  }
  const snapshots = [...byScope.values()];
  if (!snapshots.length) return null;
  return snapshots.reduce(mergeUsage);
}

function mergeUsage(left: UsageSnapshot, right: UsageSnapshot): UsageSnapshot {
  return {
    estimated_input_tokens: sum(left.estimated_input_tokens, right.estimated_input_tokens),
    estimated_output_tokens: sum(left.estimated_output_tokens, right.estimated_output_tokens),
    cached_tokens: sum(left.cached_tokens, right.cached_tokens),
    candidate_count: sum(left.candidate_count, right.candidate_count),
    revision_count: sum(left.revision_count, right.revision_count),
    elapsed_ms: sum(left.elapsed_ms, right.elapsed_ms),
    estimated_cost_usd: left.estimated_cost_usd == null && right.estimated_cost_usd == null
      ? null
      : sum(left.estimated_cost_usd ?? 0, right.estimated_cost_usd ?? 0),
  };
}

function sum(left: number, right: number) {
  return (Number(left) || 0) + (Number(right) || 0);
}

export function stageUsageTokens(usage: UsageSnapshot | null): number | null {
  if (!usage) return null;
  const total = (Number(usage.estimated_input_tokens) || 0) + (Number(usage.estimated_output_tokens) || 0);
  return total > 0 ? total : null;
}

export function stageUsageCostUsd(usage: UsageSnapshot | null): number | null {
  const cost = usage?.estimated_cost_usd;
  return typeof cost === 'number' && Number.isFinite(cost) ? cost : null;
}

export function stageUsageElapsedMs(usage: UsageSnapshot | null): number | null {
  const elapsed = Number(usage?.elapsed_ms ?? 0);
  return Number.isFinite(elapsed) && elapsed > 0 ? elapsed : null;
}
