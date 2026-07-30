import type { RunControlState, RunEvent } from '../contracts';

type ConsumeRunStreamOptions = {
  onEvent: (event: RunEvent) => void;
  response: Response;
  signal?: AbortSignal;
};

const PAUSE_EVENTS = new Set(['approval_required', 'run_paused', 'run_recovery_required']);
const FAIL_EVENTS = new Set(['node_failed', 'run_error', 'run_failed']);
const COMPLETE_EVENTS = new Set(['run_completed', 'run_export_ready']);

export async function consumeRunEventStream({
  onEvent,
  response,
  signal,
}: ConsumeRunStreamOptions): Promise<RunControlState> {
  if (!response.ok) throw new Error(`Stream request failed: ${response.status}`);
  if (!response.body) throw new Error('Stream response has no body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminal: RunControlState = 'completed';

  const abort = () => {
    try {
      reader.cancel();
    } catch {
      // Reader may already be closed.
    }
  };
  signal?.addEventListener('abort', abort, { once: true });

  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('Run stream aborted', 'AbortError');
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const parsed = drainSseEvents(buffer);
      buffer = parsed.remainder;
      for (const event of parsed.events) {
        onEvent(event);
        const nextTerminal = terminalStateForEvent(event);
        if (nextTerminal) {
          terminal = nextTerminal;
          if (nextTerminal !== 'completed') {
            abort();
            return nextTerminal;
          }
        }
      }
      if (done) break;
    }
    const parsed = drainSseEvents(`${buffer}\n\n`);
    for (const event of parsed.events) {
      onEvent(event);
      terminal = terminalStateForEvent(event) ?? terminal;
    }
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
    try {
      events.push(JSON.parse(data) as RunEvent);
    } catch (error) {
      events.push({
        type: 'run_error',
        run_id: '',
        error: error instanceof Error ? `SSE JSON parse failed: ${error.message}` : 'SSE JSON parse failed',
        message: data.slice(0, 240),
      });
    }
  }
  return { events, remainder };
}

function terminalStateForEvent(event: RunEvent): RunControlState | null {
  if (PAUSE_EVENTS.has(event.type)) return 'paused';
  if (FAIL_EVENTS.has(event.type) && event.recovery_state?.needs_recovery) return 'paused';
  if (FAIL_EVENTS.has(event.type)) return 'failed';
  if (COMPLETE_EVENTS.has(event.type)) return 'completed';
  return null;
}
