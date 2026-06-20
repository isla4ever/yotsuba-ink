import { AppHeader } from './features/pipeline/components/AppHeader';
import { KnowledgeBaseManagerDialog } from './features/pipeline/components/KnowledgeBaseManagerDialog';
import { SettingsDialog } from './features/pipeline/components/SettingsDialog';
import { PlanningWorkbench } from './features/pipeline/screens/PlanningWorkbench';
import { RunningWorkbench } from './features/pipeline/screens/RunningWorkbench';
import { useNovelWorkflowApp } from './features/pipeline/state/useNovelWorkflowApp';

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
      <SettingsDialog
        apiWarning={app.apiWarning}
        open={app.settingsOpen}
        workflow={app.workflow}
        onOpenChange={app.setSettingsOpen}
        onWorkflowChange={app.setWorkflow}
      />
      <KnowledgeBaseManagerDialog
        documents={app.knowledgeDocuments}
        onDeleted={app.handleKnowledgeDocumentDeleted}
        onDocumentsChange={app.setKnowledgeDocuments}
        onOpenChange={app.setKnowledgeManagerOpen}
        open={app.knowledgeManagerOpen}
      />
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
