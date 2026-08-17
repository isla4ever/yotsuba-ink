import type { ProviderUsageSummary, RunEvent } from '../contracts';

const emptyUsage: ProviderUsageSummary = {
  provider_operations: 0,
  succeeded_operations: 0,
  failed_operations: 0,
  pending_operations: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  reasoning_tokens: 0,
};

export function latestProviderUsage(events: RunEvent[]): ProviderUsageSummary {
  let latestSequence = -1;
  let latestUsage: ProviderUsageSummary | undefined;
  for (const event of events) {
    const usage = event.payload?.provider_usage;
    if (event.sequence > latestSequence && isProviderUsage(usage)) {
      latestSequence = event.sequence;
      latestUsage = usage;
    }
  }
  return latestUsage ?? emptyUsage;
}

function isProviderUsage(value: unknown): value is ProviderUsageSummary {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return Object.keys(emptyUsage).every((key) => (
    typeof record[key] === 'number'
    && Number.isInteger(record[key])
    && Number(record[key]) >= 0
  ));
}
