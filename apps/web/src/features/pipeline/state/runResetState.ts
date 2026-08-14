import type { RunEvent, RunInputs } from '../contracts';
import type { RunSource } from '../lib/runSource';
import type { RunState } from './runReducer';
import { hydrateLocalRunControl, type HydratedRunState } from './runState';
import type { StageDecisionState } from './stageDecisionState';

export type RunResetSnapshot = {
  hydrated: HydratedRunState;
  runSource: RunSource;
};

type ResettableRunState = Pick<RunState,
  | 'activeRunId'
  | 'paused'
  | 'runControlState'
  | 'selectedId'
  | 'stickyArtifacts'
>;

export function captureRunResetSnapshot({
  automationCockpitReady,
  decision,
  events,
  inputs,
  runSource,
  state,
}: {
  automationCockpitReady: boolean;
  decision: StageDecisionState;
  events: RunEvent[];
  inputs?: RunInputs;
  runSource: RunSource;
  state: ResettableRunState;
}): RunResetSnapshot | null {
  if (!state.activeRunId || !events.length) return null;
  const hydrated = hydrateLocalRunControl({
    activeRunId: state.activeRunId,
    events,
    inputs,
    paused: state.paused,
    runControlState: state.runControlState,
    selectedId: state.selectedId,
    stickyStageEvents: Object.values(state.stickyArtifacts.stages),
  });
  return {
    runSource,
    hydrated: {
      ...hydrated,
      ...decision,
      automationCockpitReady,
      paused: true,
      runControlState: 'paused',
      selectedId: state.selectedId,
    },
  };
}
