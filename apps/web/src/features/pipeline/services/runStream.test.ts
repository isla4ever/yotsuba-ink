import { describe, expect, it, vi } from 'vitest';
import { consumeRunEventStream } from './runStream';

describe('run stream terminal state', () => {
  it('does not treat a non-terminal EOF as run completion', async () => {
    const terminal = await consumeRunEventStream({
      onEvent: vi.fn(),
      response: sseResponse([event('node.completed', 1)]),
    });

    expect(terminal).toBeNull();
  });

  it('leaves an interrupted trailing frame for sequence replay', async () => {
    const onEvent = vi.fn();
    const complete = `data: ${JSON.stringify(event('node.completed', 1))}\n\n`;
    const response = new Response(`${complete}data: {"event_id":"interrupted`);

    const terminal = await consumeRunEventStream({ onEvent, response });

    expect(terminal).toBeNull();
    expect(onEvent.mock.calls.map(([received]) => received.sequence)).toEqual([1]);
  });

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

  it('replays resolved historical interrupts before stopping at the current one', async () => {
    const onEvent = vi.fn();
    const response = sseResponse([
      event('decision.required', 1, { decision_id: 'brief-decision' }, 'brief'),
      event('decision.resolved', 2, { decision_id: 'brief-decision' }, 'brief'),
      event('artifact.committed', 3, null, 'brief'),
      event('artifact.candidate_ready', 4, { promise: '追查失踪案' }, 'spine'),
      event('decision.required', 5, { decision_id: 'spine-decision' }, 'spine'),
    ]);

    const terminal = await consumeRunEventStream({ onEvent, response });

    expect(terminal).toBe('paused');
    expect(onEvent.mock.calls.map(([received]) => received.sequence)).toEqual([1, 2, 3, 4, 5]);
  });

  it('rejects legacy top-level event fields instead of normalizing them', async () => {
    await expect(consumeRunEventStream({
      onEvent: vi.fn(),
      response: sseResponse([{ ...event('artifact.candidate_ready', 1), artifact: { title: 'legacy' } }]),
    })).rejects.toThrow('Graph event envelope');
  });
});

function event(
  type: string,
  sequence: number,
  payload: Record<string, unknown> | null = null,
  stageId = 'detail',
) {
  return {
    event_id: `event-${sequence}`,
    sequence,
    occurred_at: '2026-08-11T00:00:00Z',
    run_id: 'run-1',
    thread_id: 'run-1',
    type,
    stage_id: stageId,
    node_id: `${stageId}.validate_contract`,
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
