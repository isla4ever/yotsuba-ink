import type { RunEvent, UsageSnapshot } from '../contracts';

/**
 * Phase 12 D6: run-level usage aggregation for the header stat. Data sources
 * are the real backend events only — `stage_usage_updated/finalized` snapshots
 * (newest per node+chapter scope wins) plus the `budget_state` carried by
 * budget events for the 用量额度 percentage. Returns null when the run has
 * reported nothing, so the header renders no placeholder.
 */

export type StageUsageRow = {
  nodeId: string;
  tokens: number | null;
  costUsd: number | null;
};

export type RunUsageSummary = {
  /** Cumulative words from the latest chapter progress snapshot. */
  words: number;
  tokens: number | null;
  costUsd: number | null;
  /** Consumed+reserved share of the run 用量额度 (0-100), when a limit exists. */
  quotaPercent: number | null;
  stages: StageUsageRow[];
};

export function runUsageSummary(events: RunEvent[]): RunUsageSummary | null {
  const byScope = new Map<string, { nodeId: string; usage: UsageSnapshot }>();
  for (const event of events) {
    if (!event.node_id || !event.usage) continue;
    if (event.type !== 'stage_usage_finalized' && event.type !== 'stage_usage_updated') continue;
    const scope = `${event.node_id}::${event.chapter ?? ''}`;
    if (!byScope.has(scope)) byScope.set(scope, { nodeId: event.node_id, usage: event.usage });
  }

  const perStage = new Map<string, { tokens: number; costUsd: number | null }>();
  for (const { nodeId, usage } of byScope.values()) {
    const row = perStage.get(nodeId) ?? { costUsd: null, tokens: 0 };
    row.tokens += (Number(usage.estimated_input_tokens) || 0) + (Number(usage.estimated_output_tokens) || 0);
    const cost = usage.estimated_cost_usd;
    if (typeof cost === 'number' && Number.isFinite(cost)) row.costUsd = (row.costUsd ?? 0) + cost;
    perStage.set(nodeId, row);
  }

  const stages: StageUsageRow[] = [...perStage.entries()].map(([nodeId, row]) => ({
    costUsd: row.costUsd,
    nodeId,
    tokens: row.tokens > 0 ? row.tokens : null,
  }));
  const totalTokens = stages.reduce((sum, row) => sum + (row.tokens ?? 0), 0);
  const totalCost = stages.reduce<number | null>(
    (sum, row) => (row.costUsd == null ? sum : (sum ?? 0) + row.costUsd),
    null,
  );
  const words = latestWordTotal(events);
  const quotaPercent = runQuotaPercent(events);

  if (!stages.length && !words && quotaPercent == null) return null;
  return {
    costUsd: totalCost,
    quotaPercent,
    stages,
    tokens: totalTokens > 0 ? totalTokens : null,
    words,
  };
}

function latestWordTotal(events: RunEvent[]): number {
  const progress = events.find((event) => event.type === 'chapter_progress_updated' && event.chapters?.length);
  if (!progress?.chapters) return 0;
  return progress.chapters.reduce((sum, item) => sum + (Number(item.words) || 0), 0);
}

function runQuotaPercent(events: RunEvent[]): number | null {
  for (const event of events) {
    const budget = event.budget_state;
    if (!budget || typeof budget !== 'object') continue;
    const max = Number((budget as Record<string, unknown>).run_max_tokens);
    if (!Number.isFinite(max) || max <= 0) continue;
    const consumed = Number((budget as Record<string, unknown>).run_consumed_tokens) || 0;
    const reserved = Number((budget as Record<string, unknown>).run_reserved_tokens) || 0;
    return Math.max(0, Math.min(100, Math.round(((consumed + reserved) / max) * 100)));
  }
  return null;
}

/** Cheap change signature for selector-equality subscriptions. */
export function runUsageSignature(summary: RunUsageSummary | null): string {
  if (!summary) return '';
  const stagePart = summary.stages
    .map((row) => `${row.nodeId}:${row.tokens ?? ''}:${row.costUsd ?? ''}`)
    .join('|');
  return `${summary.words}/${summary.tokens ?? ''}/${summary.costUsd ?? ''}/${summary.quotaPercent ?? ''}/${stagePart}`;
}

export function formatWordTotal(words: number): string {
  if (words >= 10000) return `${(words / 10000).toFixed(words >= 100000 ? 0 : 1)} 万字`;
  return `${words.toLocaleString()} 字`;
}

export function formatUsageTokens(tokens: number): string {
  if (tokens >= 10000) return `${(tokens / 10000).toFixed(1)} 万`;
  return tokens.toLocaleString();
}
