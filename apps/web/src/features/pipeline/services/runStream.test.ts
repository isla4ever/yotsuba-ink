import { describe, expect, it, vi } from 'vitest';
import { consumeRunEventStream } from './runStream';

describe('run stream recovery terminal state', () => {
  it('waits for node_failed instead of terminating on validation diagnostics', async () => {
    const onEvent = vi.fn();
    const response = sseResponse([
      { type: 'artifact_validation_failed', run_id: 'run-1', node_id: 'outline', error: 'volumes missing' },
      { type: 'node_failed', run_id: 'run-1', node_id: 'outline', error: 'volumes missing' },
    ]);

    const terminal = await consumeRunEventStream({ onEvent, response });

    expect(terminal).toBe('failed');
    expect(onEvent).toHaveBeenCalledTimes(2);
  });

  it('returns a paused terminal state for recoverable failures', async () => {
    const terminal = await consumeRunEventStream({
      onEvent: vi.fn(),
      response: sseResponse([{
        type: 'node_failed',
        run_id: 'run-1',
        node_id: 'outline',
        error: 'Provider timeout',
        recovery_state: { status: 'degraded', needs_recovery: true },
      }]),
    });

    expect(terminal).toBe('paused');
  });
});

function sseResponse(events: Array<Record<string, unknown>>) {
  const body = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}
