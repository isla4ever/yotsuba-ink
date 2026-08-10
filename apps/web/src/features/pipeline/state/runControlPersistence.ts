import type { RunControlState } from '../contracts';
import type { StoredRunControlState } from './storage';

export const runControlSaveIntervalMs = 1000;

export type RunControlSaver = {
  dispose: () => void;
  flush: () => void;
  schedule: (snapshot: StoredRunControlState) => void;
};

/**
 * Graph SSE events can arrive faster than the full run state should be
 * serialized to localStorage. Writes are
 * throttled to at most one per interval with a trailing write that always
 * persists the latest snapshot. Critical moments (pause/complete/fail,
 * beforeunload, unmount) call flush() so recovery state is never stale.
 */
export function createRunControlSaver(
  save: (snapshot: StoredRunControlState) => void,
  intervalMs = runControlSaveIntervalMs,
): RunControlSaver {
  let pending: StoredRunControlState | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const write = () => {
    if (!pending) return;
    const snapshot = pending;
    pending = null;
    save(snapshot);
  };

  const flush = () => {
    if (timer != null) {
      clearTimeout(timer);
      timer = null;
    }
    write();
  };

  return {
    dispose: () => {
      if (timer != null) clearTimeout(timer);
      timer = null;
      pending = null;
    },
    flush,
    schedule: (snapshot) => {
      pending = snapshot;
      if (timer != null) return;
      timer = setTimeout(() => {
        timer = null;
        write();
      }, intervalMs);
    },
  };
}

/** Terminal or safety-relevant moments that must hit localStorage immediately. */
export function isRunControlFlushPoint(runControlState: RunControlState, latestEventType?: string) {
  if (runControlState === 'paused' || runControlState === 'completed' || runControlState === 'failed') return true;
  return latestEventType === 'decision.required'
    || latestEventType === 'run.completed'
    || latestEventType === 'run.failed';
}
