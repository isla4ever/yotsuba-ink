import { createContext, useContext, useRef, useSyncExternalStore, type ReactNode } from 'react';
import type { ProductNavigationItem, ProductNavigationItemId } from '../layout/ProductNavigationRail';
import type { BibleSection } from '../lib/stageRoutes';
import type { StageRunStatus } from './runEventIndex';
import type { RunEventsSnapshot, RunEventsStore } from './runEventsStore';
import type { ModeRoutePolicy } from './runPresentationState';
import type {
  ExportReceipt,
  KnowledgeDocument,
  ProjectRecord,
  QualityMode,
  RunControlState,
  RunHistoryItem,
  WorkflowDefinition,
  WorkflowStage,
} from '../contracts';

/** Low-frequency per-stage runtime summary (Phase 12 F5). */
export type StageRuntimeSummary = {
  status: StageRunStatus;
  checkpointReady: boolean;
};

export type StageRuntimeSummaryMap = Record<string, StageRuntimeSummary>;

/**
 * Read-only run facts and presentation-phase state for the app shell.
 * Phase 12 F5: the raw `events` array moved to the RunEvents store — this
 * slice keeps only low-frequency summary fields so shell chrome does not
 * re-render on every streaming delta.
 */
export type RunStateSlice = {
  activeRunId: string;
  /** Effective running flag (control state OR live run events). */
  running: boolean;
  runControlState: RunControlState;
  runHasStarted: boolean;
  /** True once the current run has produced at least one event. */
  hasRunEvents: boolean;
  /** Per-stage runtime status + checkpoint readiness (value-stable). */
  stageRuntimes: StageRuntimeSummaryMap;
  approvalPending: boolean;
  infoContinueReady: boolean;
  checkpointContinueReady: boolean;
  /** True while a stage settlement transition is in flight. */
  transitioning: boolean;
  resetUndoAvailable: boolean;
  /** Control-surface phase the header/docks present (cockpit-aware). */
  workspacePhase: 'planning' | 'running';
  routePhase: 'studio' | 'history' | 'planning' | 'running' | 'bible';
  routeStageId: string;
  /** Active Story Bible section when routePhase is 'bible', otherwise ''. */
  routeBibleSection: BibleSection | '';
  /** Route-effective stage shown by the shell (header, action dock). */
  selectedStage: WorkflowStage;
  historyItems: RunHistoryItem[];
  historyLoading: boolean;
  historyError: string;
};

/** Workflow configuration facts for the app shell. */
export type WorkflowConfigSlice = {
  workflow: WorkflowDefinition;
  qualityMode: QualityMode;
  knowledgeDocuments: KnowledgeDocument[];
  saveStatus: 'idle' | 'saving' | 'saved' | 'failed';
  routePolicy: ModeRoutePolicy;
  /** Active project; null while the user is on the Studio project selector. */
  project: ProjectRecord | null;
};

/** Shell commands, navigation callbacks, and the UI state they control. */
export type UICommandSlice = {
  theme: 'dark' | 'light';
  sidebarVisible: boolean;
  sidebarExpanded: boolean;
  commandPaletteOpen: boolean;
  navigationOpen: boolean;
  navigationItems: ProductNavigationItem[];
  activeNavigationItem: ProductNavigationItemId;
  knowledgeOpen: boolean;
  historyOpen: boolean;
  settingsOpen: boolean;
  toggleTheme: () => void;
  toggleSidebar: () => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  setNavigationOpen: (open: boolean) => void;
  navigateProduct: (item: ProductNavigationItem) => void;
  navigatePlanning: () => void;
  navigateStage: (stageId: string) => void;
  navigateBible: (section: BibleSection) => void;
  openKnowledge: () => void;
  openHistory: () => void;
  openSettings: () => void;
  closeHistory: () => void;
  refreshHistory: () => Promise<void>;
  downloadHistoryExport: (item: RunHistoryItem, receipt?: ExportReceipt) => Promise<void>;
  openHistoryRun: (item: RunHistoryItem) => Promise<string>;
  branchHistoryRun: (item: RunHistoryItem) => Promise<string>;
  changeQualityMode: (mode: QualityMode) => void;
  /** Studio Shell (Phase 11.2). */
  navigateStudio: () => void;
  requestNewProject: () => void;
  openProject: (project: ProjectRecord, latestRun?: RunHistoryItem | null) => Promise<boolean>;
  saveWorkflowAsTemplate: () => Promise<string>;
  /** Primary header action: start / continue / return-to-planning. */
  runPrimaryAction: () => void;
  resetRun: () => boolean;
  undoResetRun: () => Promise<void>;
  dismissResetUndo: () => void;
};

const RunStateContext = createContext<RunStateSlice | null>(null);
const WorkflowConfigContext = createContext<WorkflowConfigSlice | null>(null);
const UICommandContext = createContext<UICommandSlice | null>(null);
const RunEventsContext = createContext<RunEventsStore | null>(null);

export function useRunStateContext(): RunStateSlice {
  const value = useContext(RunStateContext);
  if (!value) throw new Error('PipelineShellProvider is required');
  return value;
}

export function useWorkflowConfigContext(): WorkflowConfigSlice {
  const value = useContext(WorkflowConfigContext);
  if (!value) throw new Error('PipelineShellProvider is required');
  return value;
}

export function useUICommandContext(): UICommandSlice {
  const value = useContext(UICommandContext);
  if (!value) throw new Error('PipelineShellProvider is required');
  return value;
}

function useRunEventsStore(): RunEventsStore {
  const value = useContext(RunEventsContext);
  if (!value) throw new Error('PipelineShellProvider is required');
  return value;
}

/** Full run-events subscription — re-renders on every published event. */
export function useRunEvents(): RunEventsSnapshot {
  const store = useRunEventsStore();
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
}

/**
 * Selector subscription over the run-events store: the component re-renders
 * only when the selected value changes under `isEqual` (Phase 12 F5).
 */
export function useRunEventsSelector<T>(
  selector: (snapshot: RunEventsSnapshot) => T,
  isEqual: (previous: T, next: T) => boolean = Object.is,
): T {
  const store = useRunEventsStore();
  const cache = useRef<{ selector: typeof selector; snapshot: RunEventsSnapshot; value: T } | null>(null);
  const read = () => {
    const snapshot = store.getSnapshot();
    const cached = cache.current;
    // Recompute when the snapshot OR the selector closure changes (inline
    // selectors capture fresh props each render); preserve the previous value
    // reference under isEqual so unchanged selections cause no re-render.
    if (cached && cached.snapshot === snapshot && cached.selector === selector) return cached.value;
    const value = selector(snapshot);
    const preserved = cached && isEqual(cached.value, value) ? cached.value : value;
    cache.current = { selector, snapshot, value: preserved };
    return preserved;
  };
  return useSyncExternalStore(store.subscribe, read, read);
}

export function PipelineShellProvider({
  children,
  runEvents,
  runState,
  uiCommands,
  workflowConfig,
}: {
  children: ReactNode;
  runEvents: RunEventsStore;
  runState: RunStateSlice;
  uiCommands: UICommandSlice;
  workflowConfig: WorkflowConfigSlice;
}) {
  return (
    <RunEventsContext.Provider value={runEvents}>
      <RunStateContext.Provider value={runState}>
        <WorkflowConfigContext.Provider value={workflowConfig}>
          <UICommandContext.Provider value={uiCommands}>{children}</UICommandContext.Provider>
        </WorkflowConfigContext.Provider>
      </RunStateContext.Provider>
    </RunEventsContext.Provider>
  );
}
