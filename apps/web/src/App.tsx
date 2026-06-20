import { Suspense, lazy } from 'react';
import { AppHeader } from './features/pipeline/layout/AppHeader';
import { PlanningWorkbench } from './features/pipeline/planning/PlanningWorkbench';
import { useNovelWorkflowApp } from './features/pipeline/state/useNovelWorkflowApp';

const RunningWorkbench = lazy(async () => {
  const module = await import('./features/pipeline/running/RunningWorkbench');
  return { default: module.RunningWorkbench };
});

const SettingsDialog = lazy(async () => {
  const module = await import('./features/pipeline/settings/SettingsDialog');
  return { default: module.SettingsDialog };
});

const KnowledgeBaseManagerDialog = lazy(async () => {
  const module = await import('./features/pipeline/settings/KnowledgeBaseManagerDialog');
  return { default: module.KnowledgeBaseManagerDialog };
});

export function App() {
  const app = useNovelWorkflowApp();

  return (
    <main className="product-shell">
      <AppHeader
        selectedStage={app.selectedStage}
        events={app.events}
        workflow={app.workflow}
        knowledgeDocuments={app.knowledgeDocuments}
        running={app.running}
        paused={app.paused}
        theme={app.theme}
        saveStatus={app.saveStatus}
        qualityMode={app.workflow.quality_mode}
        onOpenSettings={() => {
          app.setApiWarning('');
          app.setSettingsOpen(true);
        }}
        onQualityModeChange={app.handleQualityModeChange}
        onPause={app.pauseRun}
        onRun={app.runWorkflow}
        onToggleTheme={() => app.setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
      />
      {app.workspacePhase === 'running' ? (
        <Suspense fallback={<WorkbenchFallback label="正在切换运行工作台..." />}>
          <RunningWorkbench
            activeStage={app.selectedStage}
            approvalDraft={app.approvalDraft}
            approvalPending={app.approvalPending}
            events={app.events}
            memoryEvents={app.memoryEvents}
            onApprovalDraftChange={app.setApprovalDraft}
            onApproveBrief={app.approveBrief}
            onRegenerateBrief={app.regenerateBrief}
            workflow={app.workflow}
          />
        </Suspense>
      ) : (
        <PlanningWorkbench
          workflow={app.workflow}
          selectedId={app.selectedId}
          selectedStage={app.selectedStage}
          selectedInspectorTarget={app.selectedInspectorTarget}
          events={app.events}
          knowledgeDocuments={app.knowledgeDocuments}
          onLayoutChange={app.handleLayoutChange}
          onCanvasSelect={app.handleCanvasSelect}
          onStageChange={app.handleStageChange}
          onAddModelOption={app.handleAddModelOption}
          onKnowledgeDocumentsChanged={app.refreshKnowledgeDocuments}
          onOpenKnowledgeManager={() => app.setKnowledgeManagerOpen(true)}
          onWorkflowChange={app.setWorkflow}
        />
      )}
      <Suspense fallback={null}>
        <SettingsDialog
          apiWarning={app.apiWarning}
          open={app.settingsOpen}
          workflow={app.workflow}
          onOpenChange={app.setSettingsOpen}
          onWorkflowChange={app.setWorkflow}
        />
      </Suspense>
      <Suspense fallback={null}>
        <KnowledgeBaseManagerDialog
          documents={app.knowledgeDocuments}
          onDeleted={app.handleKnowledgeDocumentDeleted}
          onDocumentsChange={app.setKnowledgeDocuments}
          onOpenChange={app.setKnowledgeManagerOpen}
          open={app.knowledgeManagerOpen}
        />
      </Suspense>
      {app.knowledgePromptOpen ? (
        <div className="knowledge-blocker-backdrop" role="presentation">
          <section className="knowledge-blocker-dialog">
            <p className="eyebrow">Knowledge Base Required</p>
            <h2>需要先构建项目知识库</h2>
            <p>{app.knowledgePrompt}</p>
            <div className="knowledge-blocker-actions">
              <button
                className="tech-button"
                onClick={() => {
                  app.setKnowledgePromptOpen(false);
                  app.setSelectedId('info');
                  app.setWorkspacePhase('planning');
                  app.setRunning(false);
                }}
              >
                返回上传资料
              </button>
              <button className="ghost" onClick={() => app.setKnowledgePromptOpen(false)}>稍后处理</button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function WorkbenchFallback({ label }: { label: string }) {
  return (
    <section className="workbench workbench-fallback" aria-live="polite">
      <div className="canvas-column">
        <section className="canvas-shell fallback-shell">
          <div className="canvas-head">
            <div>
              <p className="eyebrow">Loading Workspace</p>
              <h2>{label}</h2>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
