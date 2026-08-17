import { Suspense, lazy, useEffect, type CSSProperties } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AppHeader } from './features/pipeline/layout/AppHeader';
import { CommandPalette } from './features/pipeline/layout/CommandPalette';
import { LoadingOverlay } from './features/pipeline/layout/LoadingOverlay';
import { WorkbenchRouteTransition } from './features/pipeline/layout/WorkbenchRouteTransition';
import { WorkbenchSidebar } from './features/pipeline/layout/WorkbenchSidebar';
import { CreationHistoryPage } from './features/pipeline/layout/CreationHistoryPage';
import { defaultBibleSection, isBibleRoute, knowledgeRoute, pipelineRouteFromPath, routeForBibleSection, studioRoute, type BibleSection, type PipelinePhase } from './features/pipeline/lib/stageRoutes';
import { KnowledgeRunBlockerDialog } from './features/pipeline/settings/KnowledgeRunBlockerDialog';
import { ProviderReadinessProvider } from './features/pipeline/settings/ProviderReadinessContext';
import { PipelineShellProvider, useUICommandContext, useWorkflowConfigContext } from './features/pipeline/state/pipelineShellContext';
import { StudioKnowledgeOverview } from './features/pipeline/layout/studio/StudioKnowledgeOverview';
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

const StoryBibleWorkbench = lazy(async () => {
  const module = await import('./features/pipeline/running/bible/StoryBibleWorkbench');
  return { default: module.StoryBibleWorkbench };
});

const SettingsPage = lazy(async () => {
  const module = await import('./features/pipeline/settings/SettingsPage');
  return { default: module.SettingsPage };
});

const KnowledgeLibraryPage = lazy(async () => {
  const module = await import('./features/pipeline/settings/KnowledgeLibraryPage');
  return { default: module.KnowledgeLibraryPage };
});

const RunMonitorConsole = lazy(async () => {
  const module = await import('./features/pipeline/running/console/RunMonitorConsole');
  return { default: module.RunMonitorConsole };
});

const WorkflowTemplateEditorPage = lazy(async () => {
  const module = await import('./features/pipeline/layout/studio/WorkflowTemplateEditorPage');
  return { default: module.WorkflowTemplateEditorPage };
});

/**
 * Idle-time prefetch of every lazy route chunk: route switches then always
 * cross-fade directly instead of flashing a Suspense fallback mid-navigation.
 */
function useRouteChunkPrefetch() {
  useEffect(() => {
    const prefetch = () => {
      void import('./features/pipeline/running/RunningWorkbench');
      void import('./features/pipeline/planning/PlanningWorkbench');
      void import('./features/pipeline/running/bible/StoryBibleWorkbench');
      void import('./features/pipeline/settings/SettingsPage');
      void import('./features/pipeline/settings/KnowledgeLibraryPage');
      void import('./features/pipeline/running/console/RunMonitorConsole');
    };
    if (typeof window.requestIdleCallback === 'function') {
      const handle = window.requestIdleCallback(prefetch, { timeout: 4000 });
      return () => window.cancelIdleCallback(handle);
    }
    const timer = window.setTimeout(prefetch, 1600);
    return () => window.clearTimeout(timer);
  }, []);
}

type ShellRouteProps = {
  app: NovelWorkflowApp;
  routePhase: PipelinePhase;
  routeStageId: string;
  routeBibleSection: BibleSection | '';
  routeWorkflowId: string;
};

export function App() {
  const app = useNovelWorkflowApp();
  const { pathname } = useLocation();
  const route = pipelineRouteFromPath(pathname);
  useRouteChunkPrefetch();

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
    <ProviderReadinessProvider
      enabled={route.phase !== 'studio' && route.phase !== 'studio-knowledge' && route.phase !== 'history' && route.phase !== 'knowledge'}
      saveStatus={app.saveStatus}
      workflowId={app.workflow.id}
    >
      <AppShellProviders
        app={app}
        routeBibleSection={route.phase === 'bible' ? route.bibleSection : ''}
        routeStageId={route.stageId}
        routePhase={route.phase}
        routeWorkflowId={route.phase === 'studio-workflow' ? route.workflowId : ''}
      />
    </ProviderReadinessProvider>
  );
}

function AppShellProviders({ app, routePhase, routeStageId, routeBibleSection, routeWorkflowId }: ShellRouteProps) {
  const shell = usePipelineShellContexts({ app, routeBibleSection, routePhase, routeStageId });
  return (
    <PipelineShellProvider
      runEvents={shell.runEventsStore}
      runState={shell.runState}
      uiCommands={shell.uiCommands}
      workflowConfig={shell.workflowConfig}
    >
      <PipelineShell
        app={app}
        routeBibleSection={routeBibleSection}
        routePhase={routePhase}
        routeStageId={routeStageId}
        routeWorkflowId={routeWorkflowId}
      />
    </PipelineShellProvider>
  );
}

function PipelineShell({ app, routePhase, routeStageId, routeBibleSection, routeWorkflowId }: ShellRouteProps) {
  const navigate = useNavigate();
  const { project, qualityMode, routePolicy } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  const isStudio = routePhase === 'studio';
  const usesStudioChrome = isStudio
    || routePhase === 'history'
    || routePhase === 'studio-knowledge'
    || routePhase === 'studio-settings'
    || routePhase === 'studio-workflow';
  // The monitor console carries its own rail (book skeleton + global entries),
  // so it takes over the shell sidebar slot instead of nesting a second column.
  const monitorOwnsRail = routePhase === 'monitor';
  // Project accent immersion: one hue variable on the shell root; consumers
  // (sidebar accent mark, current-item indicator, project header) live in CSS.
  const accentStyle = project
    ? ({ '--project-accent-hue': project.accent_hue } as CSSProperties)
    : undefined;

  return (
    <main
      className={`product-shell mode-${qualityMode}${usesStudioChrome ? ' studio-shell' : ''}${routePhase === 'history' ? ' history-shell' : ''}${ui.sidebarVisible && !monitorOwnsRail ? ' has-sidebar' : ''}${monitorOwnsRail ? ' monitor-shell' : ''}${project ? ' has-project-accent' : ''}`}
      style={accentStyle}
    >
      {usesStudioChrome ? <StudioSidebar /> : monitorOwnsRail ? null : <WorkbenchSidebar />}
      <CommandPalette />
      {usesStudioChrome ? null : <AppHeader sidebarVisible={ui.sidebarVisible} />}
      <WorkbenchRouteTransition
        label={routeTransitionLabel(routePhase, app.selectedStage.label)}
        routeKey={routeTransitionKey({ routeBibleSection, routePhase, routeStageId })}
      >
      {isStudio ? (
        <StudioWorkbench />
      ) : routePhase === 'studio-knowledge' ? (
        <StudioKnowledgeOverview
          onManageProject={(target) => {
            void ui.openProject(target).then((opened) => {
              if (opened) navigate(knowledgeRoute, { replace: false });
            });
          }}
        />
      ) : routePhase === 'studio-settings' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入全局模型与服务..." />}>
          <SettingsPage
            apiWarning={app.apiWarning}
            knowledgeDocuments={app.knowledgeDocuments}
            saveStatus={app.saveStatus}
            scope="global"
            workflow={app.workflow}
            onOpenKnowledgeManager={() => navigate('/studio/knowledge', { replace: false })}
            onQualityModeChange={app.handleQualityModeChange}
            onSelectStage={() => undefined}
            onWorkflowChange={app.setWorkflow}
          />
        </Suspense>
      ) : routePhase === 'studio-workflow' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入工作流模板..." />}>
          <WorkflowTemplateEditorPage workflowId={routeWorkflowId} />
        </Suspense>
      ) : routePhase === 'history' ? (
        <CreationHistoryPage />
      ) : routePhase === 'knowledge' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入知识资料库..." />}>
          <KnowledgeLibraryPage
            documents={app.knowledgeDocuments}
            projectId={app.activeProject?.id ?? ''}
            qualityMode={app.workflow.quality_mode}
            onDeleted={app.handleKnowledgeDocumentDeleted}
            onDocumentsChange={app.setKnowledgeDocuments}
          />
        </Suspense>
      ) : routePhase === 'settings' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入模型与设置..." />}>
          <SettingsPage
            apiWarning={app.apiWarning}
            knowledgeDocuments={app.knowledgeDocuments}
            saveStatus={app.saveStatus}
            workflow={app.workflow}
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
        </Suspense>
      ) : routePhase === 'monitor' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入创作控制台..." />}>
          <RunMonitorConsole
            activeRunId={app.activeRunId}
            events={app.events}
            qualityMode={app.workflow.quality_mode}
            runControlState={app.runControlState}
            stickyArtifacts={app.stickyArtifacts}
            workflow={app.workflow}
            onOpenStageWorkbench={routePolicy.stageRoutes === 'all' ? ui.navigateStage : undefined}
          />
        </Suspense>
      ) : routePhase === 'bible' ? (
        <Suspense fallback={<WorkbenchFallback label="正在载入 Story Bible..." />}>
          <StoryBibleWorkbench section={routeBibleSection || defaultBibleSection} />
        </Suspense>
      ) : routePhase === 'running' ? (
        <Suspense fallback={<WorkbenchFallback label="正在切换运行工作台..." />}>
          <RunningWorkbench
            activeRunId={app.activeRunId}
            activeStage={routeStageId ? app.workflow.nodes.find((stage) => stage.id === routeStageId) ?? app.selectedStage : app.selectedStage}
            events={app.events}
            knowledgeDocuments={app.knowledgeDocuments}
            memoryEvents={app.memoryEvents}
            onApproveBrief={app.approveBrief}
            onContinueSettlement={app.continueSettlement}
            onOpenKnowledgeManager={ui.openKnowledge}
            onOpenConsole={routePolicy.monitor !== 'none' ? ui.openMonitor : undefined}
            onRegenerateBrief={app.regenerateBrief}
            onConfirmStageArtifact={app.confirmStageArtifact}
            onRegenerateStageDraft={app.regenerateStageDraft}
            settlementDwell={app.settlementDwell}
            settlementStageId={app.settlementStageId}
            workflow={app.workflow}
          />
        </Suspense>
      ) : (
        <Suspense fallback={<WorkbenchFallback label="正在载入创作规划..." />}>
          <PlanningWorkbench
            workflow={app.workflow}
            knowledgeDocuments={app.knowledgeDocuments}
            onStageChange={app.handleStageChange}
            onExit={ui.navigateStudio}
            onOpenKnowledgeManager={ui.openKnowledge}
            onQualityModeChange={app.handleQualityModeChange}
            onRun={app.runWorkflow}
            saveStatus={app.saveStatus}
          />
        </Suspense>
      )}
      </WorkbenchRouteTransition>
      <KnowledgeRunBlockerDialog
        message={app.knowledgePrompt}
        onClose={() => app.setKnowledgePromptOpen(false)}
        onOpenKnowledge={() => {
          app.setKnowledgePromptOpen(false);
          app.setSelectedId('brief');
          app.setWorkspacePhase('planning');
          app.setRunning(false);
          ui.openKnowledge();
        }}
        open={app.knowledgePromptOpen}
      />
    </main>
  );
}

function routeTransitionLabel(routePhase: PipelinePhase, stageLabel: string) {
  switch (routePhase) {
    case 'studio': return '作品工作室';
    case 'studio-knowledge': return '知识资料总览';
    case 'studio-settings': return '全局模型与服务';
    case 'studio-workflow': return '工作流模板配置';
    case 'history': return '创作历史';
    case 'knowledge': return '知识资料库';
    case 'settings': return '模型与设置';
    case 'monitor': return '创作控制台';
    case 'running': return `${stageLabel}阶段工作台`;
    case 'bible': return 'Story Bible 工作台';
    default: return '创作流程工作台';
  }
}

function routeTransitionKey({ routeBibleSection, routePhase, routeStageId }: {
  routeBibleSection: BibleSection | '';
  routePhase: PipelinePhase;
  routeStageId: string;
}) {
  if (routePhase === 'running') return `running-${routeStageId}`;
  if (routePhase === 'bible') return `bible-${routeBibleSection}`;
  return routePhase;
}

function WorkbenchFallback({ label }: { label: string }) {
  return <LoadingOverlay contained detail="正在恢复项目状态与阶段产物，请稍候。" eyebrow="正在载入" title={label} />;
}
