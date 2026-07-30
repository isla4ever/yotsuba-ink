import { describe, expect, it } from 'vitest';
import type { RunEvent, UsageSnapshot } from '../contracts';
import { stageUsageCostUsd, stageUsageElapsedMs, stageUsageFromEvents, stageUsageTokens } from './stageUsage';

describe('stageUsageFromEvents (D1)', () => {
  it('returns null when the backend reported no usage, so panels can render 暂无', () => {
    const events: RunEvent[] = [
      { type: 'node_completed', run_id: 'run-1', node_id: 'outline' },
    ];
    const usage = stageUsageFromEvents(events, 'outline');
    expect(usage).toBeNull();
    expect(stageUsageTokens(usage)).toBeNull();
    expect(stageUsageCostUsd(usage)).toBeNull();
    expect(stageUsageElapsedMs(usage)).toBeNull();
  });

  it('reads the real stage_usage events, newest first, scoped to the stage', () => {
    const events: RunEvent[] = [
      usageEvent('stage_usage_finalized', 'outline', { elapsed_ms: 3000, estimated_input_tokens: 100, estimated_output_tokens: 50, estimated_cost_usd: 0.5 }),
      usageEvent('stage_usage_updated', 'outline', { elapsed_ms: 1500, estimated_input_tokens: 40, estimated_output_tokens: 10, estimated_cost_usd: 0.1 }),
      usageEvent('stage_usage_finalized', 'summary', { elapsed_ms: 9000, estimated_input_tokens: 999, estimated_output_tokens: 999, estimated_cost_usd: 9 }),
    ];
    const usage = stageUsageFromEvents(events, 'outline');
    expect(stageUsageElapsedMs(usage)).toBe(3000);
    expect(stageUsageTokens(usage)).toBe(150);
    expect(stageUsageCostUsd(usage)).toBe(0.5);
  });

  it('sums chapter-scoped usage and keeps cost null when no scope is priced', () => {
    const events: RunEvent[] = [
      usageEvent('stage_usage_finalized', 'text', { elapsed_ms: 2000, estimated_input_tokens: 20, estimated_output_tokens: 5, estimated_cost_usd: null }, '第二章'),
      usageEvent('stage_usage_finalized', 'text', { elapsed_ms: 1000, estimated_input_tokens: 10, estimated_output_tokens: 5, estimated_cost_usd: null }, '第一章'),
    ];
    const usage = stageUsageFromEvents(events, 'text');
    expect(stageUsageElapsedMs(usage)).toBe(3000);
    expect(stageUsageTokens(usage)).toBe(40);
    expect(stageUsageCostUsd(usage)).toBeNull();
  });
});

function usageEvent(type: string, nodeId: string, usage: Partial<UsageSnapshot>, chapter?: string): RunEvent {
  return {
    type,
    run_id: 'run-1',
    node_id: nodeId,
    chapter,
    usage: {
      estimated_input_tokens: 0,
      estimated_output_tokens: 0,
      cached_tokens: 0,
      candidate_count: 1,
      revision_count: 0,
      elapsed_ms: 0,
      ...usage,
    },
  };
}
