import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import type {
  InspectorTarget,
  KnowledgeDocument,
  RunControlState,
  RunEvent,
  WorkflowDefinition,
} from '../contracts';
import { getPreferredRunSource, type RunSource } from '../lib/runSource';
import { listKnowledgeDocuments } from '../services/knowledge';
import { saveWorkflowDefinition } from '../services/workflowApi';
import { buildRunInputs } from './runInputs';
import {
  createInitialRunState,
  runReducer,
  stageIdForRunEventNavigation,
} from './runReducer';
import {
  indexedHasRecoverableRun,
  indexedRunningNodeExists,
} from './runEventIndex';
import {
  selectStage,
  sortRunEventsNewestFirst,
} from './runSelectors';
import {
  loadRunControlLocally,
  saveRunControlLocally,
  workflowWithActiveRunMode,
  workflowWithStoredPreferences,
} from './storage';
import { createRunControlSaver, isRunControlFlushPoint } from './runControlPersistence';
import { useProjectSession } from './useProjectSession';
import { useRunCommands } from './useRunCommands';
import { useRunHistory } from './useRunHistory';
import { useRunHistoryActions } from './useRunHistoryActions';
import { useRunRecovery } from './useRunRecovery';
import { useRunResetSafety } from './useRunResetSafety';
import { useRunStreamController } from './useRunStreamController';
import { useRunTransitions } from './useRunTransitions';
import { useStageDecision } from './useStageDecision';
import { useThemeMode } from './useThemeMode';
import { useWorkflowAutosave } from './useWorkflowAutosave';
import { useWorkflowActions } from './useWorkflowActions';
import { defaultWorkflow } from './defaultWorkflow';

export function useNovelWorkflowApp() {
  // The project session must initialize first: it sets the storage scope every
  // subsequent stored-state initializer reads from (Phase 11.2 mine 1).
  const projectSession = useProjectSession();
  const activeProject = projectSession.activeProject;
  const [storedRunControl] = useState(() => loadRunControlLocally());
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(() => (
    workflowWithActiveRunMode(workflowWithStoredPreferences(defaultWorkflow), storedRunControl)
  ));
  const storedEvents = useMemo(
    () => sortRunEventsNewestFirst(storedRunControl.events ?? []),
    [storedRunControl.events],
  );
  const [runState, dispatchRun] = useReducer(runReducer, {
    activeRunId: storedRunControl.activeRunId,
    events: storedEvents,
    paused: storedRunControl.paused,
    runControlState: storedRunControl.runControlState,
    selectedId: storedRunControl.selectedId,
    stageId: workflow.nodes[0].id,
    workspacePhase: storedRunControl.workspacePhase,
  }, createInitialRunState);
  const eventsRef = useRef<RunEvent[]>(storedEvents);
  const [runSource, setRunSource] = useState<RunSource>(
    storedRunControl.runSource ?? getPreferredRunSource(),
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [knowledgeManagerOpen, setKnowledgeManagerOpen] = useState(false);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocument[]>([]);
  const [apiWarning, setApiWarning] = useState('');
  const [workflowHydrated, setWorkflowHydrated] = useState(false);
  const [runRecoveryHydrated, setRunRecoveryHydrated] = useState(() => !storedRunControl.activeRunId);
  const { theme, setTheme } = useThemeMode();
  const { saveStatus, suppressWorkflowSave } = useWorkflowAutosave(
    workflow,
    saveWorkflowDefinition,
    workflowHydrated,
  );
  const transitions = useRunTransitions({ dispatchRun, stages: workflow.nodes });
  const history = useRunHistory();

  const setKnowledgePromptOpen = useCallback((open: boolean) => {
    dispatchRun({ type: 'knowledge_prompt_open_changed', open });
  }, []);
  const setRunning = useCallback((running: boolean) => {
    dispatchRun({ type: 'control_changed', control: { running } });
  }, []);
  const setRunControl = useCallback((control: {
    paused: boolean;
    runControlState: RunControlState;
    running: boolean;
  }) => {
    dispatchRun({ type: 'control_changed', control });
  }, []);
  const setSelectedId = useCallback((selectedId: string) => {
    dispatchRun({ type: 'selected_id_changed', selectedId });
  }, []);
  const setSelectedInspectorTarget = useCallback((target: InspectorTarget) => {
    dispatchRun({ type: 'selected_inspector_changed', target });
  }, []);
  const setWorkspacePhase = useCallback((workspacePhase: 'planning' | 'running') => {
    dispatchRun({ type: 'workspace_changed', workspacePhase });
  }, []);

  const selectedStage = useMemo(
    () => selectStage(workflow.nodes, runState.selectedId),
    [runState.selectedId, workflow.nodes],
  );
  const runInputs = useMemo(
    () => buildRunInputs(workflow, runSource, activeProject),
    [activeProject, runSource, workflow],
  );
  const stageDecision = useStageDecision({
    activeRunId: runState.activeRunId,
    emitEvent: applyEvent,
    eventsRef,
    onWarning: setApiWarning,
    runSource,
    setRunControl,
    workflow,
  });
  const stream = useRunStreamController(applyEvent);
  const commands = useRunCommands({
    dispatchRun,
    emitEvent: applyEvent,
    eventsRef,
    history,
    onSettingsRequired: () => setSettingsOpen(true),
    onWarning: setApiWarning,
    project: activeProject,
    runInputs,
    runSource,
    setRunSource,
    stageDecision,
    state: runState,
    storedRunSource: storedRunControl.runSource,
    stream,
    transitions,
    workflow,
  });
  const runResetSafety = useRunResetSafety({
    automationCockpitReady: transitions.automationCockpitReady,
    decision: stageDecision.state,
    eventsRef,
    onReset: commands.resetRunControl,
    onRestore: commands.restoreRecoveredRun,
    runSource,
    setRunSource,
    state: runState,
  });
  const workflowActions = useWorkflowActions({
    clearRunState: commands.clearRunState,
    decision: stageDecision.state,
    eventsRef,
    runState,
    setSelectedId,
    setSelectedInspectorTarget,
    setWorkflow,
  });
  const initialRecovery = useRunRecovery({
    enabled: workflowHydrated,
    stored: storedRunControl,
    onDiscard: commands.clearRunState,
    onRestore: commands.restoreRecoveredRun,
    onSettled: () => setRunRecoveryHydrated(true),
    onWorkflow: (runWorkflow) => {
      suppressWorkflowSave(runWorkflow);
      setWorkflow(runWorkflow);
    },
    onWarning: setApiWarning,
  });
  const historyActions = useRunHistoryActions({
    activeRunId: runState.activeRunId,
    cancelInitialRecovery: initialRecovery.cancel,
    historyRefresh: history.refresh,
    onProjectContext: projectSession.switchProjectContext,
    onRestore: commands.restoreRecoveredRun,
    onWarning: setApiWarning,
    runControlState: runState.runControlState,
    running: runState.running,
    suppressWorkflowSave,
    setRunSource,
    setWorkflow,
    stopActiveStream: stream.invalidate,
  });

  // Late-bound collaborators for the project session (deps-ref pattern; see useProjectSession).
  projectSession.bind({
    cancelInitialRecovery: initialRecovery.cancel,
    clearRunState: commands.clearRunState,
    onHydrated: () => setWorkflowHydrated(true),
    onWarning: setApiWarning,
    openRun: historyActions.openRun,
    runFacts: {
      activeRunId: runState.activeRunId,
      runControlState: runState.runControlState,
      running: runState.running,
      selectedId: runState.selectedId,
      workspacePhase: runState.workspacePhase,
    },
    setWorkflow,
    suppressWorkflowSave,
    workflowId: workflow.id,
    workflowName: workflow.name,
  });

  useEffect(() => {
    setKnowledgeDocuments([]);
    void refreshKnowledgeDocuments().catch((error) => {
      setApiWarning(error instanceof Error ? `知识库列表加载失败：${error.message}` : '知识库列表加载失败。');
    });
  }, [activeProject?.id]);

  // Phase 12 F2: throttle full-state localStorage writes to <=1/s (trailing);
  // pause/complete/fail and page exit flush immediately so recovery stays fresh.
  const runControlSaver = useMemo(() => createRunControlSaver(saveRunControlLocally), []);
  useEffect(() => {
    runControlSaver.schedule({
      activeRunId: runState.activeRunId,
      events: eventsRef.current,
      paused: runState.paused,
      runSource,
      runControlState: runState.runControlState,
      selectedId: runState.selectedId,
      workspacePhase: runState.workspacePhase,
    });
    if (isRunControlFlushPoint(runState.runControlState, runState.events[0]?.type)) {
      runControlSaver.flush();
    }
  }, [
    runControlSaver,
    runSource,
    runState.activeRunId,
    runState.events,
    runState.paused,
    runState.runControlState,
    runState.selectedId,
    runState.workspacePhase,
  ]);
  useEffect(() => {
    const flush = () => runControlSaver.flush();
    window.addEventListener('beforeunload', flush);
    return () => {
      window.removeEventListener('beforeunload', flush);
      runControlSaver.flush();
    };
  }, [runControlSaver]);

  async function refreshKnowledgeDocuments() {
    setKnowledgeDocuments(await listKnowledgeDocuments(activeProject?.id ?? 'default'));
  }

  function applyEvent(event: RunEvent) {
    eventsRef.current = [event, ...eventsRef.current].slice(0, 500);
    dispatchRun({ type: 'event_received', event });
    stageDecision.applyEvent(event);
    const navigationStageId = stageIdForRunEventNavigation(event);
    if (navigationStageId) transitions.notifyStageNavigation(navigationStageId);
    if (
      event.type === 'stage_summary_ready'
      && event.node_id
      && event.node_id !== 'info'
      && workflow.quality_mode !== 'deep'
    ) {
      // Fast/balanced auto-advance never blocks (D7); the cockpit surfaces an
      // expandable settlement summary card instead of a dwelling overlay.
      transitions.startSettlement({
        kind: 'cockpit_auto',
        nextStageId: String(event.next_step ?? ''),
        stageId: event.node_id,
      });
    }
  }

  return {
    ...runState,
    ...workflowActions,
    activeProject,
    apiWarning,
    approvalDraft: stageDecision.state.approvalDraft,
    approvalPending: stageDecision.state.approvalPending,
    automationCockpitReady: transitions.automationCockpitReady,
    checkpointContinueReady: stageDecision.state.checkpointContinueReady,
    checkpointStageId: stageDecision.state.checkpointStageId,
    infoContinueReady: stageDecision.state.infoContinueReady,
    continueSettlement: transitions.continueSettlement,
    settlementDwell: transitions.settlementDwell,
    settlementStageId: transitions.settlementStageId,
    knowledgeDocuments,
    knowledgeManagerOpen,
    historyError: history.error,
    historyItems: history.items,
    historyLoading: history.loading,
    dismissRunResetUndo: runResetSafety.dismissRunResetUndo,
    refreshHistory: history.refresh,
    downloadHistoryExport: historyActions.downloadExport,
    openHistoryRun: historyActions.openRun,
    openProject: projectSession.openProject,
    restoreHistoryCheckpoint: historyActions.restoreCheckpoint,
    saveWorkflowAsTemplate: projectSession.saveWorkflowAsTemplate,
    sessionHydrated: workflowHydrated && runRecoveryHydrated,
    // Phase 12 F6: index-backed hot selectors — these run on every app render,
    // and the old scans were O(n)/O(n*m) over up to 500 events.
    runHasStarted: indexedHasRecoverableRun(
      runState.activeRunId,
      runState.eventIndex,
      runState.runControlState,
    ),
    runIsActiveFromEvents: indexedRunningNodeExists(runState.eventIndex),
    runResetUndoAvailable: runResetSafety.runResetUndoAvailable,
    resetRunControl: runResetSafety.resetRunControl,
    refreshKnowledgeDocuments,
    returnExportToPlanning: commands.returnExportToPlanning,
    regenerateBrief: stageDecision.regenerateBrief,
    regenerateStageDraft: stageDecision.regenerateStageDraft,
    requestVariantCompare: stageDecision.requestVariantCompare,
    runWorkflow: commands.runWorkflow,
    saveStatus,
    selectedStage,
    setApprovalDraft: stageDecision.setApprovalDraft,
    setApiWarning,
    setKnowledgeDocuments,
    setKnowledgeManagerOpen,
    setKnowledgePromptOpen,
    setRunStageNavigator: transitions.setStageNavigator,
    setRunning,
    setSelectedId,
    setSelectedInspectorTarget,
    setSettingsOpen,
    setTheme,
    setWorkflow,
    setWorkspacePhase,
    settingsOpen,
    theme,
    undoRunReset: runResetSafety.undoRunReset,
    workflow,
    approveBrief: stageDecision.approveBrief,
    confirmStageArtifact: stageDecision.confirmStageArtifact,
    selectBalancedVariant: stageDecision.selectBalancedVariant,
    selectDraftCandidate: stageDecision.selectDraftCandidate,
  };
}

export type NovelWorkflowApp = ReturnType<typeof useNovelWorkflowApp>;
