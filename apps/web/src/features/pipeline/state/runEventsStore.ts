import type { RunEvent } from '../contracts';
import { buildRunEventIndex, emptyRunEventIndex, type RunEventIndex } from './runEventIndex';

/**
 * Phase 12 F5: high-frequency run events leave the shell context slices and
 * travel through this external store instead. Shell chrome (header, sidebar,
 * command palette) subscribes only to low-frequency summary fields, while
 * event-driven visualizations subscribe here with selectors — a streaming
 * delta re-renders only the leaf that actually reads it.
 */

export type RunEventsSnapshot = {
  events: RunEvent[];
  index: RunEventIndex;
};

export type RunEventsStore = {
  getSnapshot: () => RunEventsSnapshot;
  subscribe: (listener: () => void) => () => void;
  publish: (next: RunEventsSnapshot) => void;
};

export function emptyRunEventsSnapshot(): RunEventsSnapshot {
  return { events: [], index: emptyRunEventIndex() };
}

export function runEventsSnapshotFrom(events: RunEvent[]): RunEventsSnapshot {
  return { events, index: buildRunEventIndex(events) };
}

export function createRunEventsStore(initial: RunEventsSnapshot = emptyRunEventsSnapshot()): RunEventsStore {
  let snapshot = initial;
  const listeners = new Set<() => void>();
  return {
    getSnapshot: () => snapshot,
    publish: (next) => {
      if (next.events === snapshot.events && next.index === snapshot.index) return;
      snapshot = next;
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
