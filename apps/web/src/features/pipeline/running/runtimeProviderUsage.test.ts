import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { latestProviderUsage } from './runtimeProviderUsage';

describe('latestProviderUsage', () => {
  it('reads the newest receipted usage projection without inventing values', () => {
    const events = [event(2, 780), event(3, 1240)];

    expect(latestProviderUsage(events)).toMatchObject({
      provider_operations: 3,
      total_tokens: 1240,
    });
  });

  it('returns a zero projection when SSE has not projected usage yet', () => {
    expect(latestProviderUsage([])).toMatchObject({
      provider_operations: 0,
      total_tokens: 0,
    });
  });
});

function event(providerOperations: number, totalTokens: number): RunEvent {
  return {
    event_id: `node-${providerOperations}`,
    sequence: providerOperations,
    occurred_at: '2026-08-11T00:00:00Z',
    run_id: 'run-1',
    thread_id: 'run-1',
    type: 'node.completed',
    stage_id: 'info',
    node_id: 'info.generate_candidate',
    chapter_id: '',
    status: 'completed',
    payload: {
      provider_usage: {
        provider_operations: providerOperations,
        succeeded_operations: providerOperations,
        failed_operations: 0,
        pending_operations: 0,
        prompt_tokens: Math.floor(totalTokens * 0.7),
        completion_tokens: Math.ceil(totalTokens * 0.3),
        total_tokens: totalTokens,
        reasoning_tokens: 0,
      },
    },
    payload_ref: '',
    checkpoint_id: '',
  };
}
