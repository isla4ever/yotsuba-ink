import type { RunControlState, RunEvent } from '../contracts';

type ConsumeRunStreamOptions = {
  onEvent?: (event: RunEvent) => void | Promise<void>;
  /**
   * Batch sink: receives every event decoded from one read chunk at once.
   * Replaying a finished run arrives as a few large chunks, so handling them as
   * batches keeps the console from repainting itself event by event.
   */
  onEvents?: (events: RunEvent[]) => void | Promise<void>;
  response: Response;
  signal?: AbortSignal;
};

const PAUSE_EVENTS = new Set(['decision.required']);
const FAIL_EVENTS = new Set(['run.failed']);
const COMPLETE_EVENTS = new Set(['run.completed']);

export async function consumeRunEventStream({
  onEvent,
  onEvents,
  response,
  signal,
}: ConsumeRunStreamOptions): Promise<RunControlState | null> {
  if (!response.ok) throw new Error(`Stream request failed: ${response.status}`);
  if (!response.body) throw new Error('Stream response has no body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminal: RunControlState | null = null;

  const abort = () => {
    try {
      reader.cancel();
    } catch {
      // Reader may already be closed.
    }
  };
  signal?.addEventListener('abort', abort, { once: true });

  const deliver = async (events: RunEvent[]) => {
    if (!events.length) return;
    if (onEvents) await onEvents(events);
    for (const event of events) {
      if (!onEvents && onEvent) await onEvent(event);
      terminal = controlStateForEvent(event, terminal);
    }
  };

  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('Run stream aborted', 'AbortError');
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const parsed = drainSseEvents(buffer);
      buffer = parsed.remainder;
      await deliver(parsed.events);
      if (done) break;
    }
    // A trailing frame without the SSE blank-line delimiter was interrupted in
    // transit. The controller reconnects from the last delivered sequence.
    return terminal;
  } finally {
    signal?.removeEventListener('abort', abort);
  }
}

function drainSseEvents(buffer: string) {
  const events: RunEvent[] = [];
  const normalized = buffer.replace(/\r\n/g, '\n');
  const chunks = normalized.split('\n\n');
  const remainder = chunks.pop() ?? '';
  for (const chunk of chunks) {
    const data = chunk
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n');
    if (!data || data === '[DONE]') continue;
    events.push(parseRunEvent(data));
  }
  return { events, remainder };
}

function parseRunEvent(data: string): RunEvent {
  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch (error) {
    throw new Error(error instanceof Error ? `SSE JSON parse failed: ${error.message}` : 'SSE JSON parse failed');
  }
  if (!isRunEvent(value)) throw new Error('SSE event does not match the Graph event envelope');
  return value;
}

function isRunEvent(value: unknown): value is RunEvent {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const event = value as Record<string, unknown>;
  const keys = [
    'event_id', 'sequence', 'occurred_at', 'run_id', 'thread_id', 'type',
    'stage_id', 'node_id', 'chapter_id', 'status', 'payload', 'payload_ref', 'checkpoint_id',
  ];
  if (Object.keys(event).some((key) => !keys.includes(key))) return false;
  return keys.every((key) => key in event)
    && typeof event.event_id === 'string'
    && typeof event.sequence === 'number'
    && Number.isInteger(event.sequence)
    && event.sequence >= 1
    && typeof event.occurred_at === 'string'
    && typeof event.run_id === 'string'
    && typeof event.thread_id === 'string'
    && typeof event.type === 'string'
    && (event.stage_id === null || typeof event.stage_id === 'string')
    && typeof event.node_id === 'string'
    && typeof event.chapter_id === 'string'
    && typeof event.status === 'string'
    && (event.payload === null || (typeof event.payload === 'object' && !Array.isArray(event.payload)))
    && typeof event.payload_ref === 'string'
    && typeof event.checkpoint_id === 'string';
}

function controlStateForEvent(
  event: RunEvent,
  current: RunControlState | null,
): RunControlState | null {
  if (PAUSE_EVENTS.has(event.type)) return 'paused';
  if (event.type === 'decision.resolved') return null;
  if (FAIL_EVENTS.has(event.type)) return 'failed';
  if (COMPLETE_EVENTS.has(event.type)) return 'completed';
  return current;
}
