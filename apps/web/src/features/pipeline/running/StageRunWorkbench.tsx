import { AnimatePresence } from 'motion/react';
import { useState } from 'react';
import type { KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { InfoStageLoadingOverlay } from './InfoStageLoadingOverlay';
import { infoStageLoadingVisible } from './infoStageLoadingState';
import { RuntimeInsights } from './RuntimeInsights';
import type { RuntimeInsightContext } from './RuntimeInsightPanel';
import { RuntimeSideDetailSheet } from './RuntimeSideDetailSheet';
import { StageRunMainArea } from './StageRunMainArea';
import { currentStageArtifact, type StageArtifactDraft } from './stageArtifactState';
import { StageSettlementOverlay } from './StageSettlementOverlay';
import { stageRuntimeLayout, type RuntimePanelKey } from './stageRuntimeLayout';
import { latestApprovedArtifact, latestResult } from './stageRunUtils';
import { runtimeArtifactProjection } from './runtimeArtifactProjection';
import { useActiveRunDefinition } from '../state/useActiveRunDefinition';

type Props = {
  activeRunId: string;
  events: RunEvent[];
  memoryEvents: RunEvent[];
  settlementStageId: string;
  /** Phase 12 D7: dwellable settlement (user 「继续」 + 4s auto-continue). */
  settlementDwell: boolean;
  onContinueSettlement: () => void;
  workflow: WorkflowDefinition;
  activeStage: WorkflowStage;
  approvalDraft: string;
  approvalPending: boolean;
  knowledgeDocuments: KnowledgeDocument[];
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onOpenKnowledgeManager: () => void;
  onOpenWorkbench?: () => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
  onConfirmStageArtifact: (stageId: string, artifact?: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
};

export function StageRunWorkbench({
  activeRunId,
  approvalDraft,
  approvalPending,
  events,
  knowledgeDocuments,
  memoryEvents,
  onApprovalDraftChange,
  onApproveBrief,
  onContinueSettlement,
  onOpenKnowledgeManager,
  onOpenWorkbench,
  onRegenerateBrief,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  workflow,
  activeStage,
  settlementDwell,
  settlementStageId,
}: Props) {
  const [stageArtifactDrafts, setStageArtifactDrafts] = useState<Record<string, StageArtifactDraft>>({});
  const [sideDetailPanel, setSideDetailPanel] = useState<RuntimePanelKey | null>(null);
  const runDefinition = useActiveRunDefinition(activeRunId);
  const runtimeLayout = stageRuntimeLayout[activeStage.type];
  const hasSidePanels = runtimeLayout.primary.length > 0 || runtimeLayout.compact.length > 0;
  const hasContextRail = hasSidePanels && runtimeLayout.primary.length === 0 && runtimeLayout.compact.length > 0;
  const infoArtifact = latestApprovedArtifact(events, 'info') || latestResult(events, 'info') || approvalDraft;
  const characterArtifact = latestApprovedArtifact(events, 'characters') || latestResult(events, 'characters');
  const summaryBaselineArtifact = latestApprovedArtifact(events, 'summary') || latestResult(events, 'summary');
  const summarySource = activeStage.type === 'summary' ? latestResult(events, activeStage.id) : summaryBaselineArtifact;
  const summaryDraft = stageArtifactDrafts[activeStage.id];
  const summaryValue = summaryDraft?.source === summarySource ? summaryDraft.value : summarySource;
  const outlineBaselineArtifact = latestApprovedArtifact(events, 'outline') || latestResult(events, 'outline');
  const outlineSource = activeStage.type === 'outline' ? latestResult(events, activeStage.id) : outlineBaselineArtifact;
  const outlineDraft = stageArtifactDrafts[activeStage.id];
  const outlineValue = outlineDraft?.source === outlineSource ? outlineDraft.value : outlineSource;
  const detailBaselineArtifact = latestApprovedArtifact(events, 'detail') || latestResult(events, 'detail');
  const detailSource = activeStage.type === 'detail' ? latestResult(events, activeStage.id) : detailBaselineArtifact;
  const detailDraft = stageArtifactDrafts[activeStage.id];
  const detailValue = detailDraft?.source === detailSource ? detailDraft.value : detailSource;
  const projection = runtimeArtifactProjection({
    activeStageType: activeStage.type,
    characters: characterArtifact,
    detail: detailValue,
    events,
    info: infoArtifact,
    outline: outlineValue,
    summary: summaryValue,
  });

  const insightContext: RuntimeInsightContext = {
    artifactProjection: projection.stage,
    events,
    characterGraphOverride: projection.characterGraph,
    infoWorldbuilding: projection.worldbuilding,
    knowledgeDocuments,
    memoryEvents,
    onOpenKnowledgeManager,
    writebackStatus: projection.writeback,
    workflow,
  };

  return (
    <section className={`stage-run-workbench${hasSidePanels ? '' : ' no-side-panels'}${hasContextRail ? ' context-rail-layout' : ''}`}>
      <InfoStageLoadingOverlay events={events} visible={activeStage.type === 'info' && infoStageLoadingVisible(activeRunId, events)} />
      <StageSettlementOverlay
        dwell={settlementDwell}
        events={events}
        onContinue={onContinueSettlement}
        open={Boolean(settlementStageId)}
        stage={workflow.nodes.find((stage) => stage.id === settlementStageId) ?? activeStage}
      />
      <StageRunMainArea
        activeRunId={activeRunId}
        approvalDraft={approvalDraft}
        approvalPending={approvalPending}
        events={events}
        onApprovalDraftChange={onApprovalDraftChange}
        onApproveBrief={onApproveBrief}
        onConfirmStageArtifact={onConfirmStageArtifact}
        onOpenWorkbench={onOpenWorkbench}
        onOpenRuntimePanel={setSideDetailPanel}
        onRegenerateBrief={onRegenerateBrief}
        onRegenerateStageDraft={onRegenerateStageDraft}
        onStageArtifactDraftChange={(stageId, source, value) => {
          setStageArtifactDrafts((current) => ({ ...current, [stageId]: { source, value } }));
        }}
        stage={activeStage}
        stageArtifactDraft={stageArtifactDrafts[activeStage.id]}
        runDefinition={runDefinition.definition}
        workflow={workflow}
      />
      <RuntimeInsights
        {...insightContext}
        activeStage={activeStage}
        compactPanelKeys={runtimeLayout.compact}
        panelKeys={runtimeLayout.primary}
        visible={hasSidePanels}
        onOpenPanel={setSideDetailPanel}
      />
      <AnimatePresence>
        {sideDetailPanel ? (
          <RuntimeSideDetailSheet
            {...insightContext}
            panel={sideDetailPanel}
            onClose={() => setSideDetailPanel(null)}
          />
        ) : null}
      </AnimatePresence>
    </section>
  );
}
