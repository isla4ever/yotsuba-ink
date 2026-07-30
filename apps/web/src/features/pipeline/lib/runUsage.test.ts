import { describe, expect, it } from 'vitest';
import { runUsageSummary } from './runUsage';
import type { RunEvent, UsageSnapshot } from '../contracts';

function usage(input: number, output: number, cost: number | null = null, elapsed = 1000): UsageSnapshot {
  return {
    cached_tokens: 0,
    candidate_count: 1,
    elapsed_ms: elapsed,
    estimated_cost_usd: cost,
    estimated_input_tokens: input,
    estimated_output_tokens: output,
    revision_count: 0,
  };
}

describe('runUsageSummary (D6)', () => {
  it('returns null without usage/word/budget data so the header renders nothing', () => {
    expect(runUsageSummary([])).toBeNull();
    expect(runUsageSummary([{ type: 'chapter_delta', run_id: 'r', node_id: 'text' } as RunEvent])).toBeNull();
  });

  it('aggregates newest usage per stage+chapter scope and sums words from chapter progress', () => {
    // Newest-first: the finalized summary event supersedes the earlier update in the same scope.
    const events = [
      { type: 'stage_usage_finalized', run_id: 'r', node_id: 'text', chapter: '第1章', usage: usage(500, 700, 0.02) },
      { type: 'stage_usage_updated', run_id: 'r', node_id: 'text', chapter: '第1章', usage: usage(100, 100, 0.005) },
      { type: 'stage_usage_updated', run_id: 'r', node_id: 'text', chapter: '第2章', usage: usage(200, 300, null) },
      { type: 'stage_usage_finalized', run_id: 'r', node_id: 'summary', usage: usage(1000, 2000, 0.05) },
      {
        type: 'chapter_progress_updated',
        run_id: 'r',
        node_id: 'text',
        chapters: [
          { volume: '卷一', chapter: '第1章', status: 'completed', words: 3100, quality_score: 0.9, node_id: 'text' },
          { volume: '卷一', chapter: '第2章', status: 'running', words: 900, quality_score: 0, node_id: 'text' },
        ],
      },
    ] as RunEvent[];
    const summary = runUsageSummary(events);
    expect(summary?.words).toBe(4000);
    expect(summary?.tokens).toBe(500 + 700 + 200 + 300 + 1000 + 2000);
    expect(summary?.costUsd).toBeCloseTo(0.07, 5);
    expect(summary?.quotaPercent).toBeNull();
    const text = summary?.stages.find((row) => row.nodeId === 'text');
    expect(text?.tokens).toBe(1700);
    expect(text?.costUsd).toBeCloseTo(0.02, 5);
  });

  it('derives the 用量额度 percentage from the newest budget_state snapshot', () => {
    const events = [
      {
        type: 'stage_budget_warning',
        run_id: 'r',
        node_id: 'text',
        budget_state: { run_max_tokens: 100000, run_consumed_tokens: 70000, run_reserved_tokens: 12000 },
      },
      {
        type: 'run_budget_warning',
        run_id: 'r',
        budget_state: { run_max_tokens: 100000, run_consumed_tokens: 10000, run_reserved_tokens: 0 },
      },
    ] as RunEvent[];
    expect(runUsageSummary(events)?.quotaPercent).toBe(82);
  });
});
