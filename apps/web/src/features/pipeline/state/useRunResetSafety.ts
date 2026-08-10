import { useEffect, useState, type MutableRefObject } from 'react';
import type { RunEvent, RunInputs } from '../contracts';
import type { RunSource } from '../lib/runSource';
import type { RunState } from './runReducer';
import { captureRunResetSnapshot, type RunResetSnapshot } from './runResetState';
import type { HydratedRunState } from './runState';
import type { StageDecisionState } from './stageDecisionState';

const undoWindowMs = 15_000;

type Props = {
  automationCockpitReady: boolean;
  decision: StageDecisionState;
  eventsRef: MutableRefObject<RunEvent[]>;
  runInputs: RunInputs;
  onReset: () => void;
  onRestore: (hydrated: HydratedRunState, reconnect: boolean) => Promise<void>;
  runSource: RunSource;
  setRunSource: (source: RunSource) => void;
  state: Pick<RunState, 'activeRunId' | 'paused' | 'runControlState' | 'selectedId'>;
};

export function useRunResetSafety({
  automationCockpitReady,
  decision,
  eventsRef,
  runInputs,
  onReset,
  onRestore,
  runSource,
  setRunSource,
  state,
}: Props) {
  const [undoSnapshot, setUndoSnapshot] = useState<RunResetSnapshot | null>(null);

  useEffect(() => {
    if (!undoSnapshot) return undefined;
    const timer = window.setTimeout(() => setUndoSnapshot(null), undoWindowMs);
    return () => window.clearTimeout(timer);
  }, [undoSnapshot]);

  useEffect(() => {
    if (
      undoSnapshot
      && state.activeRunId
      && state.activeRunId !== undoSnapshot.hydrated.activeRunId
    ) {
      setUndoSnapshot(null);
    }
  }, [state.activeRunId, undoSnapshot]);

  function resetRunControl() {
    if (!state.activeRunId) return false;
    const snapshot = captureRunResetSnapshot({
      automationCockpitReady,
      decision,
      events: eventsRef.current,
      inputs: runInputs,
      runSource,
      state,
    });
    onReset();
    setUndoSnapshot(snapshot);
    return true;
  }

  async function undoRunReset() {
    const snapshot = undoSnapshot;
    if (!snapshot || state.activeRunId) return '';
    setUndoSnapshot(null);
    setRunSource(snapshot.runSource);
    await onRestore(snapshot.hydrated, false);
    return snapshot.hydrated.selectedId;
  }

  return {
    dismissRunResetUndo: () => setUndoSnapshot(null),
    resetRunControl,
    runResetUndoAvailable: Boolean(undoSnapshot),
    undoRunReset,
  };
}
