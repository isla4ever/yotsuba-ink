import { describe, expect, it, vi } from 'vitest';
import { consumeRunEventStream } from './runStream';

describe('run stream terminal state', () => {
  it('stops only on the stable run.failed event', async () => {
    const onEvent = vi.fn();
    const response = sseResponse([
      event('node.failed', 1),
      event('run.failed', 2),
    ]);

    const terminal = await consumeRunEventStream({ onEvent, response });

    expect(terminal).toBe('failed');
    expect(onEvent).toHaveBeenCalledTimes(2);
  });

  it('returns a paused terminal state at an interrupt', async () => {
    const terminal = await consumeRunEventStream({
      onEvent: vi.fn(),
      response: sseResponse([event('decision.required', 1, { decision_id: 'decision-1' })]),
    });

    expect(terminal).toBe('paused');
  });

  it('rejects legacy top-level event fields instead of normalizing them', async () => {
    await expect(consumeRunEventStream({
      onEvent: vi.fn(),
      response: sseResponse([{ ...event('artifact.candidate_ready', 1), artifact: { title: 'legacy' } }]),
    })).rejects.toThrow('Graph event envelope');
  });
});

function event(type: string, sequence: number, payload: Record<string, unknown> | null = null) {
  return {
    event_id: `event-${sequence}`,
    sequence,
    occurred_at: '2026-08-11T00:00:00Z',
    run_id: 'run-1',
    thread_id: 'run-1',
    type,
    stage_id: 'outline',
    node_id: 'outline.validate_contract',
    chapter_id: '',
    status: '',
    payload,
    payload_ref: '',
    checkpoint_id: '',
  };
}

function sseResponse(events: Array<Record<string, unknown>>) {
  const body = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}
