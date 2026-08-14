import type { ReactNode } from 'react';
import { defaultWorkflow } from './defaultWorkflow';
import {
  PipelineShellProvider,
  type RunStateSlice,
  type StageRuntimeSummaryMap,
  type UICommandSlice,
  type WorkflowConfigSlice,
} from './pipelineShellContext';
import { buildRunEventIndex } from './runEventIndex';
import { createRunEventsStore, runEventsSnapshotFrom } from './runEventsStore';
import { modeRoutePolicy } from './runPresentationState';
import { stageRuntimeSummaryMap } from './useStageRuntimes';
import type { RunEvent } from '../contracts';

/**
 * Test-only harness: renders shell components under the pipeline shell
 * contexts with neutral defaults. Not imported by application code.
 */

export function buildTestRunState(overrides: Partial<RunStateSlice> = {}): RunStateSlice {
  return {
    activeRunId: '',
    approvalPending: false,
    checkpointContinueReady: false,
    hasRunEvents: false,
    historyError: '',
    historyItems: [],
    historyLoading: false,
    briefContinueReady: false,
    resetUndoAvailable: false,
    routeBibleSection: '',
    routePhase: 'planning',
    routeStageId: '',
    runControlState: 'idle',
    runHasStarted: false,
    running: false,
    selectedStage: defaultWorkflow.nodes[0],
    stageRuntimes: {},
    transitioning: false,
    workspacePhase: 'planning',
    ...overrides,
  };
}

/** Derives the F5 shell summary fields the way the app shell does (from events). */
export function buildTestRunFacts(events: RunEvent[]): Pick<RunStateSlice, 'hasRunEvents' | 'stageRuntimes'> & { stageRuntimes: StageRuntimeSummaryMap } {
  return {
    hasRunEvents: events.length > 0,
    stageRuntimes: stageRuntimeSummaryMap(buildRunEventIndex(events), defaultWorkflow.nodes),
  };
}

export function buildTestWorkflowConfig(overrides: Partial<WorkflowConfigSlice> = {}): WorkflowConfigSlice {
  return {
    knowledgeDocuments: [],
    project: null,
    qualityMode: defaultWorkflow.quality_mode,
    routePolicy: modeRoutePolicy(defaultWorkflow.quality_mode, false),
    saveStatus: 'idle',
    workflow: defaultWorkflow,
    ...overrides,
  };
}

export function buildTestUICommands(overrides: Partial<UICommandSlice> = {}): UICommandSlice {
  const noop = () => undefined;
  return {
    activeNavigationItem: 'planning',
    changeQualityMode: noop,
    closeCommandPalette: noop,
    closeHistory: noop,
    commandPaletteOpen: false,
    dismissResetUndo: noop,
    downloadHistoryExport: async () => undefined,
    historyOpen: false,
    knowledgeOpen: false,
    navigateBible: noop,
    navigatePlanning: noop,
    navigateProduct: noop,
    navigateStage: noop,
    navigateStudio: noop,
    navigationItems: [],
    navigationOpen: false,
    openCommandPalette: noop,
    openHistory: noop,
    openHistoryRun: async () => '',
    openKnowledge: noop,
    openProject: async () => false,
    openMonitor: noop,
    openSettings: noop,
    refreshHistory: async () => undefined,
    requestNewProject: noop,
    resetRun: () => false,
    branchHistoryRun: async () => '',
    runPrimaryAction: noop,
    saveWorkflowAsTemplate: async () => '',
    setNavigationOpen: noop,
    monitorOpen: false,
    settingsOpen: false,
    sidebarExpanded: true,
    sidebarVisible: true,
    theme: 'dark',
    toggleSidebar: noop,
    toggleTheme: noop,
    undoResetRun: async () => undefined,
    ...overrides,
  };
}

export function PipelineShellTestProviders({
  children,
  events = [],
  runState,
  uiCommands,
  workflowConfig,
}: {
  children: ReactNode;
  /** Events published to the run-events store (and reflected into F5 facts). */
  events?: RunEvent[];
  runState?: Partial<RunStateSlice>;
  uiCommands?: Partial<UICommandSlice>;
  workflowConfig?: Partial<WorkflowConfigSlice>;
}) {
  return (
    <PipelineShellProvider
      runEvents={createRunEventsStore(runEventsSnapshotFrom(events))}
      runState={buildTestRunState({ ...(events.length ? buildTestRunFacts(events) : {}), ...runState })}
      uiCommands={buildTestUICommands(uiCommands)}
      workflowConfig={buildTestWorkflowConfig(workflowConfig)}
    >
      {children}
    </PipelineShellProvider>
  );
}
