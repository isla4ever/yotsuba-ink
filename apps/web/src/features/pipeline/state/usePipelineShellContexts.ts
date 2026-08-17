import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { productNavigationIcons, type ProductNavigationItem, type ProductNavigationItemId } from '../layout/ProductNavigationRail';
import { useSidebarPreference } from '../layout/useSidebarPreference';
import { historyRoute, knowledgeRoute, monitorRoute, routeForBibleSection, routeForStage, settingsRoute, studioKnowledgeRoute, studioRoute, studioSettingsRoute, type BibleSection, type PipelinePhase } from '../lib/stageRoutes';
import type { RunStateSlice, UICommandSlice, WorkflowConfigSlice } from './pipelineShellContext';
import { createRunEventsStore } from './runEventsStore';
import { canNavigateToStage, modeRoutePolicy } from './runPresentationState';
import type { NovelWorkflowApp } from './useNovelWorkflowApp';
import { usePipelineShellRouting } from './usePipelineShellRouting';
import { useSidebarViewport } from './useSidebarViewport';
import { useStageRuntimes } from './useStageRuntimes';

type Params = {
  app: NovelWorkflowApp;
  routePhase: PipelinePhase;
  routeStageId: string;
  routeBibleSection: BibleSection | '';
};

/**
 * Groups the useNovelWorkflowApp return value into the three shell context
 * slices (run state / workflow config / UI commands). Pure regrouping — no
 * new behavior; one useMemo per slice keeps references stable.
 */
export function usePipelineShellContexts({ app, routePhase, routeStageId, routeBibleSection }: Params) {
  const navigate = useNavigate();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const sidebarViewport = useSidebarViewport();
  const sidebarPreference = useSidebarPreference(sidebarViewport.wide);
  const {
    activeRunId,
    activeProject,
    approvalPending,
    checkpointContinueReady,
    dismissRunResetUndo,
    downloadHistoryExport,
    events,
    eventIndex,
    handleQualityModeChange,
    historyError,
    historyItems,
    historyLoading,
    briefContinueReady,
    knowledgeDocuments,
    openHistoryRun,
    openProject,
    refreshHistory,
    resetRunControl,
    branchHistoryRun,
    completeExportAndStay,
    runControlState,
    runHasStarted,
    runIsActiveFromEvents,
    runResetUndoAvailable,
    running,
    runWorkflow,
    saveStatus,
    saveWorkflowAsTemplate,
    selectedId,
    selectedStage,
    setApiWarning,
    setRunStageNavigator,
    setSelectedId,
    setSelectedInspectorTarget,
    setTheme,
    settlementStageId,
    setWorkspacePhase,
    theme,
    undoRunReset,
    workflow,
    workspacePhase,
  } = app;

  // Phase 12 F5: high-frequency events go through an external store; shell
  // slices below carry only low-frequency summaries derived from the index.
  // Created once and then fed via publish(); the effect below keeps it current.
  const [runEventsStore] = useState(() => createRunEventsStore({ events, index: eventIndex }));
  useEffect(() => {
    runEventsStore.publish({ events, index: eventIndex });
  }, [eventIndex, events, runEventsStore]);
  const stageRuntimes = useStageRuntimes(eventIndex, workflow.nodes);
  const hasRunEvents = eventIndex.size > 0;

  const routePolicy = useMemo(() => modeRoutePolicy(workflow.quality_mode), [workflow.quality_mode]);
  const runControlActive = ['starting', 'running', 'stop_requested'].includes(runControlState) || running || runIsActiveFromEvents;
  const runAttached = activeRunId !== '' && (hasRunEvents || runControlActive);
  /** Browse routes keep presenting the underlying workspace phase in shared controls. */
  const presentedPhase: 'planning' | 'running' = routePhase === 'planning' || routePhase === 'running'
    ? routePhase
    : workspacePhase;
  const controlPhase = presentedPhase;
  const headerStage = useMemo(
    () => (routePhase === 'running' && routeStageId
      ? workflow.nodes.find((stage) => stage.id === routeStageId) ?? selectedStage
      : selectedStage),
    [routePhase, routeStageId, selectedStage, workflow.nodes],
  );

  useEffect(() => {
    setNavigationOpen(false);
  }, [routePhase, routeStageId]);

  usePipelineShellRouting({
    routePhase,
    routePolicy,
    routeStageId,
    // The monitor must keep presenting terminal runs (failed/completed), so it
    // gates on attachment rather than the recoverable-run flag that drops the
    // moment a run.failed / run.completed event lands.
    runAttached,
    selectedId,
    setRunStageNavigator,
    setSelectedId,
    setSelectedInspectorTarget,
    setWorkspacePhase,
    workspacePhase,
  });

  const navigationItems = useMemo<ProductNavigationItem[]>(() => [
    ...(runAttached ? [{
      id: 'running',
      label: '当前运行',
      description: '打开当前运行工作台',
      icon: productNavigationIcons.running,
      badge: selectedStage.label,
    } satisfies ProductNavigationItem] : [{
      id: 'planning',
      label: '创作准备',
      description: '完善故事起点、资料与创作模式',
      icon: productNavigationIcons.planning,
    } satisfies ProductNavigationItem]),
    { id: 'knowledge', label: '知识资料', description: '管理项目资料与检索依据', icon: productNavigationIcons.knowledge, badge: knowledgeDocuments.length ? String(knowledgeDocuments.length) : undefined },
    { id: 'history', label: '创作历史', description: '查看运行、快照与导出版本', icon: productNavigationIcons.history, badge: historyItems.length ? String(historyItems.length) : undefined },
    { id: 'settings', label: '模型与设置', description: '编辑服务、模型和工作流偏好', icon: productNavigationIcons.settings },
  ], [historyItems.length, knowledgeDocuments.length, runAttached, selectedStage.label]);

  const activeNavigationItem: ProductNavigationItemId = routePhase === 'settings'
    ? 'settings'
    : routePhase === 'history'
      ? 'history'
      : routePhase === 'knowledge'
        ? 'knowledge'
        : controlPhase === 'running'
          ? 'running'
          : 'planning';

  const runState = useMemo<RunStateSlice>(() => ({
    activeRunId,
    approvalPending,
    checkpointContinueReady,
    hasRunEvents,
    historyError,
    historyItems,
    historyLoading,
    briefContinueReady,
    resetUndoAvailable: runResetUndoAvailable,
    routeBibleSection,
    routePhase,
    routeStageId,
    runControlState,
    runHasStarted,
    running: running || runIsActiveFromEvents,
    selectedStage: headerStage,
    stageRuntimes,
    transitioning: Boolean(settlementStageId),
    workspacePhase: controlPhase,
  }), [
    activeRunId, approvalPending, checkpointContinueReady, controlPhase, hasRunEvents,
    headerStage, historyError, historyItems, historyLoading, briefContinueReady,
    routeBibleSection, routePhase, routeStageId, runControlState, runHasStarted, runIsActiveFromEvents,
    running, runResetUndoAvailable, settlementStageId, stageRuntimes,
  ]);

  const workflowConfig = useMemo<WorkflowConfigSlice>(() => ({
    knowledgeDocuments,
    project: activeProject,
    qualityMode: workflow.quality_mode,
    routePolicy,
    saveStatus,
    workflow,
  }), [activeProject, knowledgeDocuments, routePolicy, saveStatus, workflow]);

  const uiCommands = useMemo<UICommandSlice>(() => {
    const openKnowledge = () => navigate(knowledgeRoute, { replace: false });
    const openHistory = () => {
      navigate(historyRoute, { replace: false });
      void refreshHistory();
    };
    const openSettings = () => {
      setApiWarning('');
      navigate(settingsRoute, { replace: false });
    };
    const workspaceRoute = () => {
      if (!runAttached) return '/planning';
      return routePolicy.monitor === 'default' ? monitorRoute : routeForStage(selectedStage.id);
    };
    const navigatePlanning = () => navigate(workspaceRoute(), { replace: false });
    const openMonitor = () => navigate(monitorRoute, { replace: false });
    const navigateStage = (stageId: string) => {
      if (canNavigateToStage(routePolicy, stageId)) navigate(routeForStage(stageId), { replace: false });
    };
    const navigateBible = (section: BibleSection) => navigate(routeForBibleSection(section), { replace: false });
    const navigateStudio = () => navigate(studioRoute, { replace: false });
    return {
      activeNavigationItem,
      changeQualityMode: handleQualityModeChange,
      closeCommandPalette: () => setCommandPaletteOpen(false),
      closeHistory: () => navigate(workspaceRoute(), { replace: false }),
      commandPaletteOpen,
      dismissResetUndo: dismissRunResetUndo,
      downloadHistoryExport,
      historyOpen: routePhase === 'history',
      knowledgeOpen: routePhase === 'knowledge',
      monitorOpen: routePhase === 'monitor',
      navigateBible,
      navigatePlanning,
      navigateStudio,
      openProject: async (project, latestRun) => {
        const result = await openProject(project, latestRun ?? null);
        if (!result.ok) return false;
        if (!result.stageId) {
          navigate('/planning', { replace: false });
        } else if (routePolicy.monitor === 'default' || !canNavigateToStage(routePolicy, result.stageId)) {
          // Fast mode (and any mode without per-stage routes) lands restored
          // sessions on the monitor console instead of a stage route.
          navigate(monitorRoute, { replace: false });
        } else {
          navigate(routeForStage(result.stageId), { replace: false });
        }
        return true;
      },
      requestNewProject: () => navigate(`${studioRoute}?new=1`, { replace: false }),
      saveWorkflowAsTemplate,
      navigateProduct: (item: ProductNavigationItem) => {
        setNavigationOpen(false);
        if (item.disabled) return;
        if (item.id === 'planning') return navigatePlanning();
        if (item.id === 'running') {
          if (routePolicy.monitor === 'default') openMonitor();
          else if (routePolicy.stageRoutes === 'all') navigate(routeForStage(selectedStage.id), { replace: false });
          else navigate(workspaceRoute(), { replace: false });
          return;
        }
        if (item.id === 'knowledge') return openKnowledge();
        if (item.id === 'history') return openHistory();
        openSettings();
      },
      navigateStage,
      navigationItems,
      navigationOpen,
      openCommandPalette: () => setCommandPaletteOpen(true),
      openHistory,
      openHistoryRun: async (item) => {
        const stageId = await openHistoryRun(item);
        if (stageId) navigate(routeForStage(stageId), { replace: false });
        return stageId;
      },
      openKnowledge,
      openMonitor,
      openSettings,
      refreshHistory,
      resetRun: () => {
        const reset = resetRunControl();
        if (reset) navigate('/planning', { replace: true });
        return reset;
      },
      branchHistoryRun: async (item) => {
        const stageId = await branchHistoryRun(item);
        if (stageId) navigate(routeForStage(stageId), { replace: false });
        return stageId;
      },
      runPrimaryAction: () => {
        if (checkpointContinueReady && headerStage.type === 'export') {
          completeExportAndStay();
          navigate(routePolicy.monitor === 'default' ? monitorRoute : routeForStage('export'), { replace: true });
          return;
        }
        void runWorkflow();
      },
      setNavigationOpen,
      settingsOpen: routePhase === 'settings',
      sidebarExpanded: sidebarPreference.expanded,
      sidebarVisible: sidebarViewport.desktop,
      theme,
      toggleSidebar: sidebarPreference.toggle,
      toggleTheme: () => setTheme((current) => (current === 'dark' ? 'light' : 'dark')),
      undoResetRun: async () => {
        const stageId = await undoRunReset();
        if (stageId) navigate(routeForStage(stageId), { replace: false });
      },
    };
  }, [
    activeNavigationItem, checkpointContinueReady, commandPaletteOpen, dismissRunResetUndo,
    downloadHistoryExport, handleQualityModeChange, headerStage,
    navigate, navigationItems, navigationOpen, openHistoryRun, openProject, refreshHistory, resetRunControl,
    branchHistoryRun, completeExportAndStay, routePolicy, runAttached, runWorkflow, saveWorkflowAsTemplate, selectedStage.id,
    setApiWarning, setTheme,
    routePhase,
    sidebarPreference.expanded, sidebarPreference.toggle, sidebarViewport.desktop, theme, undoRunReset,
  ]);

  return { runEventsStore, runState, uiCommands, workflowConfig };
}
