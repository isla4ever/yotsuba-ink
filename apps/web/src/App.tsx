import { Suspense, lazy, useRef, type CSSProperties } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AppHeader } from './features/pipeline/layout/AppHeader';
import { CommandPalette } from './features/pipeline/layout/CommandPalette';
import { LoadingOverlay } from './features/pipeline/layout/LoadingOverlay';
import { WorkbenchRouteTransition } from './features/pipeline/layout/WorkbenchRouteTransition';
import { WorkbenchSidebar } from './features/pipeline/layout/WorkbenchSidebar';
import { CreationHistoryPage } from './features/pipeline/layout/CreationHistoryPage';
import { defaultBibleSection, isBibleRoute, pipelineRouteFromPath, routeForBibleSection, studioRoute, type BibleSection } from './features/pipeline/lib/stageRoutes';
import { KnowledgeRunBlockerDialog } from './features/pipeline/settings/KnowledgeRunBlockerDialog';
import { ProviderReadinessProvider } from './features/pipeline/settings/ProviderReadinessContext';
import { PipelineShellProvider, useUICommandContext, useWorkflowConfigContext } from './features/pipeline/state/pipelineShellContext';
import { StudioSidebar } from './features/pipeline/layout/studio/StudioSidebar';
import { StudioWorkbench } from './features/pipeline/layout/studio/StudioWorkbench';
import { useNovelWorkflowApp, type NovelWorkflowApp } from './features/pipeline/state/useNovelWorkflowApp';
import { usePipelineShellContexts } from './features/pipeline/state/usePipelineShellContexts';

const RunningWorkbench = lazy(async () => {
  const module = await import('./features/pipeline/running/RunningWorkbench');
  return { default: module.RunningWorkbench };
});

const PlanningWorkbench = lazy(async () => {
  const module = await import('./features/pipeline/planning/PlanningWorkbench');
  return { default: module.PlanningWorkbench };
});

const ProductionCockpitWorkbench = lazy(async () => {
  const module = await import('./features/pipeline/planning/ProductionCockpitWorkbench');
  return { default: module.ProductionCockpitWorkbench };
});

const StoryBibleWorkbench = lazy(async () => {
  const module = await import('./features/pipeline/running/bible/StoryBibleWorkbench');
  return { default: module.StoryBibleWorkbench };
});

const SettingsDialog = lazy(async () => {
  const module = await import('./features/pipeline/settings/SettingsDialog');
  return { default: module.SettingsDialog };
});

const KnowledgeBaseManagerDialog = lazy(async () => {
  const module = await import('./features/pipeline/settings/KnowledgeBaseManagerDialog');
  return { default: module.KnowledgeBaseManagerDialog };
});

type ShellRouteProps = {
  app: NovelWorkflowApp;
  routePhase: 'studio' | 'history' | 'planning' | 'running' | 'bible';
  routeStageId: string;
  routeBibleSection: BibleSection | '';
};

export function App() {
  const app = useNovelWorkflowApp();
  const { pathname } = useLocation();
  const route = pipelineRouteFromPath(pathname);

  if (!route) {
    // /studio is the default landing page; an active project session keeps
    // landing back in its Creation Shell (localStorage-based, mine 1 scope).
    const fallback = app.activeProject ? '/planning' : studioRoute;
    return <Navigate replace to={isBibleRoute(pathname) ? routeForBibleSection(defaultBibleSection) : fallback} />;
  }
  if (!app.sessionHydrated) {
    return (
      <main aria-busy="true" className={`product-shell mode-${app.workflow.quality_mode}`}>
        <WorkbenchFallback label="正在恢复创作现场..." />
      </main>
    );
  }
  return (
    <ProviderReadinessProvider enabled={route.phase !== 'studio' && route.phase !== 'history'} workflowId={app.workflow.id}>
      <AppShellProviders
        app={app}
        routeBibleSection={route.phase === 'bible' ? route.bibleSection : ''}
        routeStageId={route.stageId}
        routePhase={route.phase}
      />
    </ProviderReadinessProvider>
  );
}

function AppShellProviders({ app, routePhase, routeStageId, routeBibleSection }: ShellRouteProps) {
  const shell = usePipelineShellContexts({ app, routeBibleSection, routePhase, routeStageId });
  return (
    <PipelineShellProvider
      runEvents={shell.runEventsStore}
      runState={shell.runState}
      uiCommands={shell.uiCommands}
      workflowConfig={shell.workflowConfig}
    >
      <PipelineShell app={app} routeBibleSection={routeBibleSection} routeStageId={routeStageId} routePhase={routePhase} />
    </PipelineShellProvider>
  );
}

function PipelineShell({ app, routePhase, routeStageId, routeBibleSection }: ShellRouteProps) {
  const navigate = useNavigate();
  const { project, qualityMode, routePolicy } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  const isStudio = routePhase === 'studio';
  const usesStudioChrome = isStudio || routePhase === 'history';
  const cockpitVisible = routePhase === 'planning' && routePolicy.planningSurface === 'cockpit';
  const cockpitMode = qualityMode === 'balanced' ? 'balanced' : 'fast';
  const runHasStarted = app.runHasStarted;
  const settingsLoadedRef = useRef(false);
  if (app.settingsOpen) settingsLoadedRef.current = true;
  // Project accent immersion: one hue variable on the shell root; consumers
  // (sidebar accent mark, current-item indicator, project header) live in CSS.
  const accentStyle = project
    ? ({ '--project-accent-hue': project.accent_hue } as CSSProperties)
    : undefined;

  return (
    <main
      className={`product-shell mode-${qualityMode}${usesStudioChrome ? ' studio-shell' : ''}${routePhase === 'history' ? ' history-shell' : ''}${ui.sidebarVisible ? ' has-sidebar' : ''}${project ? ' has-project-accent' : ''}`}
      style={accentStyle}
    >
      {usesStudioChrome ? <StudioSidebar /> : <WorkbenchSidebar />}
      <CommandPalette />
      {usesStudioChrome ? null : <AppHeader sidebarVisible={ui.sidebarVisible} />}
      <WorkbenchRouteTransition
        label={isStudio ? '作品工作室' : routePhase === 'history' ? '创作历史' : routePhase === 'running' ? `${app.selectedStage.label}阶段工作台` : routePhase === 'bible' ? 'Story Bible 工作台' : '创作流程工作台'}
        routeKey={isStudio ? 'studio' : routePhase === 'history' ? 'history' : routePhase === 'running' ? `running-${routeStageId}` : routePhase === 'bible' ? `bible-${routeBibleSection}` : cockpitVisible ? `cockpit-${cockpitMode}` : 'planning'}
      >
      {isStudio ? (
        <StudioWorkbench />
      ) : routePhase === 'history' ? (
        <CreationHistoryPage />
      ) : routePhase === 'bible' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入 Story Bible..." />}>
          <StoryBibleWorkbench section={routeBibleSection || defaultBibleSection} />
        </Suspense>
      ) : routePhase === 'running' ? (
        <Suspense fallback={<WorkbenchFallback label="正在切换运行工作台..." />}>
          <RunningWorkbench
            activeRunId={app.activeRunId}
            activeStage={routeStageId ? app.workflow.nodes.find((stage) => stage.id === routeStageId) ?? app.selectedStage : app.selectedStage}
            approvalDraft={app.approvalDraft}
            approvalPending={app.approvalPending}
            events={app.events}
            knowledgeDocuments={app.knowledgeDocuments}
            memoryEvents={app.memoryEvents}
            onApprovalDraftChange={app.setApprovalDraft}
            onApproveBrief={app.approveBrief}
            onContinueSettlement={app.continueSettlement}
            onOpenKnowledgeManager={ui.openKnowledge}
            onOpenWorkbench={ui.navigatePlanning}
            onRegenerateBrief={app.regenerateBrief}
            onConfirmStageArtifact={app.confirmStageArtifact}
            onRegenerateStageDraft={app.regenerateStageDraft}
            settlementDwell={app.settlementDwell}
            settlementStageId={app.settlementStageId}
            workflow={app.workflow}
          />
        </Suspense>
      ) : cockpitVisible ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入创作驾驶舱..." />}>
          <ProductionCockpitWorkbench
            key={`${app.workflow.quality_mode}-${app.automationCockpitReady ? 'auto' : 'direct'}`}
            workflow={app.workflow}
            selectedId={app.selectedId}
            selectedStage={app.selectedStage}
            events={app.events}
            knowledgeDocuments={app.knowledgeDocuments}
            mode={cockpitMode}
            runHasStarted={runHasStarted}
            onCanvasSelect={app.handleCanvasSelect}
            onAddModelOption={app.handleAddModelOption}
            onLayoutChange={app.handleLayoutChange}
            onOpenKnowledgeManager={ui.openKnowledge}
            onStageChange={app.handleStageChange}
          />
        </Suspense>
      ) : (
        <Suspense fallback={<WorkbenchFallback label="正在载入创作规划..." />}>
          <PlanningWorkbench
            workflow={app.workflow}
            selectedId={app.selectedId}
            selectedStage={app.selectedStage}
            events={app.events}
            knowledgeDocuments={app.knowledgeDocuments}
            onLayoutChange={app.handleLayoutChange}
            onCanvasSelect={app.handleCanvasSelect}
            onStageChange={app.handleStageChange}
            onAddModelOption={app.handleAddModelOption}
            onOpenKnowledgeManager={ui.openKnowledge}
            onOpenStage={ui.navigateStage}
            onQualityModeChange={app.handleQualityModeChange}
            onRun={app.runWorkflow}
            onWorkflowChange={app.setWorkflow}
            runHasStarted={runHasStarted}
            saveStatus={app.saveStatus}
          />
        </Suspense>
      )}
      </WorkbenchRouteTransition>
      <Suspense fallback={null}>
        {settingsLoadedRef.current ? (
          <SettingsDialog
            apiWarning={app.apiWarning}
            knowledgeDocuments={app.knowledgeDocuments}
            open={app.settingsOpen}
            saveStatus={app.saveStatus}
            workflow={app.workflow}
            onOpenChange={app.setSettingsOpen}
            onOpenKnowledgeManager={ui.openKnowledge}
            onQualityModeChange={app.handleQualityModeChange}
            onSelectStage={(stageId) => {
              app.setSelectedId(stageId);
              app.setSelectedInspectorTarget({ kind: 'stage', id: stageId });
              app.setWorkspacePhase('planning');
              navigate('/planning', { replace: false });
            }}
            onWorkflowChange={app.setWorkflow}
          />
        ) : null}
      </Suspense>
      <Suspense fallback={null}>
        <KnowledgeBaseManagerDialog
          documents={app.knowledgeDocuments}
          projectId={app.activeProject?.id ?? ''}
          qualityMode={app.workflow.quality_mode}
          onDeleted={app.handleKnowledgeDocumentDeleted}
          onDocumentsChange={app.setKnowledgeDocuments}
          onOpenChange={app.setKnowledgeManagerOpen}
          open={app.knowledgeManagerOpen}
        />
      </Suspense>
      <KnowledgeRunBlockerDialog
        message={app.knowledgePrompt}
        onClose={() => app.setKnowledgePromptOpen(false)}
        onOpenKnowledge={() => {
          app.setKnowledgePromptOpen(false);
          app.setSelectedId('info');
          app.setWorkspacePhase('planning');
          app.setRunning(false);
          ui.openKnowledge();
        }}
        open={app.knowledgePromptOpen}
      />
    </main>
  );
}

function WorkbenchFallback({ label }: { label: string }) {
  return <LoadingOverlay contained detail="正在恢复项目状态与阶段产物，请稍候。" eyebrow="正在载入" title={label} />;
}
