import type { RunEvent } from './run';

let nextSequence = 1;

export function runEvent(type: string, overrides: Partial<RunEvent> = {}): RunEvent {
  const sequence = overrides.sequence ?? nextSequence++;
  const runId = overrides.run_id ?? 'test-run';
  return {
    event_id: overrides.event_id ?? `${runId}:event:${sequence}`,
    sequence,
    occurred_at: overrides.occurred_at ?? new Date(sequence * 1000).toISOString(),
    run_id: runId,
    thread_id: overrides.thread_id ?? runId,
    type,
    stage_id: overrides.stage_id ?? null,
    node_id: overrides.node_id ?? '',
    chapter_id: overrides.chapter_id ?? '',
    status: overrides.status ?? '',
    payload: overrides.payload ?? null,
    payload_ref: overrides.payload_ref ?? '',
    checkpoint_id: overrides.checkpoint_id ?? '',
  };
}
