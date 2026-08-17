import { AnimatePresence } from 'motion/react';
import { useState } from 'react';
import type { KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { BriefStageLoadingOverlay } from './BriefStageLoadingOverlay';
import { briefStageLoadingVisible } from './briefStageLoadingState';
import { RuntimeInsights } from './RuntimeInsights';
import type { RuntimeInsightContext } from './RuntimeInsightPanel';
import { RuntimeSideDetailSheet } from './RuntimeSideDetailSheet';
import { StageRunMainArea } from './StageRunMainArea';
import { currentStageArtifact } from './stageArtifactState';
import { StageSettlementOverlay } from './StageSettlementOverlay';
import { stageRuntimeLayout, type RuntimePanelKey } from './stageRuntimeLayout';
import { latestApprovedArtifact, latestResult } from './stageRunUtils';
import { runtimeArtifactProjection } from './runtimeArtifactProjection';
import { useActiveRunDefinition } from '../state/useActiveRunDefinition';
import { useChapterContextManifest } from '../state/useChapterContextManifest';
import { useStageArtifactDraft } from '../state/useStageArtifactDraft';

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
  knowledgeDocuments: KnowledgeDocument[];
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onOpenKnowledgeManager: () => void;
  onOpenConsole?: () => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
  onConfirmStageArtifact: (stageId: string, artifact?: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
};

export function StageRunWorkbench({
  activeRunId,
  events,
  knowledgeDocuments,
  memoryEvents,
  onApproveBrief,
  onContinueSettlement,
  onOpenKnowledgeManager,
  onOpenConsole,
  onRegenerateBrief,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  workflow,
  activeStage,
  settlementDwell,
  settlementStageId,
}: Props) {
  const [sideDetailPanel, setSideDetailPanel] = useState<RuntimePanelKey | null>(null);
  const runDefinition = useActiveRunDefinition(activeRunId);
  const contextManifest = useChapterContextManifest(
    activeRunId,
    events.reduce((max, event) => Math.max(max, Number(event.sequence) || 0), 0),
    activeStage.type === 'text',
  );
  const runtimeLayout = stageRuntimeLayout[activeStage.type];
  const hasSidePanels = runtimeLayout.primary.length > 0 || runtimeLayout.compact.length > 0;
  const hasContextRail = hasSidePanels && runtimeLayout.primary.length === 0 && runtimeLayout.compact.length > 0;
  const briefArtifact = latestApprovedArtifact(events, 'brief') || latestResult(events, 'brief');
  const activeStageSource = latestResult(events, activeStage.id);
  const stageDraftPersistence = useStageArtifactDraft({
    events,
    runId: activeRunId,
    source: activeStageSource,
    stageId: activeStage.id,
  });
  const castArtifact = latestApprovedArtifact(events, 'cast') || latestResult(events, 'cast');
  const spineBaselineArtifact = latestApprovedArtifact(events, 'spine') || latestResult(events, 'spine');
  const spineSource = activeStage.type === 'spine' ? latestResult(events, activeStage.id) : spineBaselineArtifact;
  const spineDraft = activeStage.type === 'spine' ? stageDraftPersistence.draft : undefined;
  const spineValue = spineDraft?.source === spineSource ? spineDraft.value : spineSource;
  const volumesBaselineArtifact = latestApprovedArtifact(events, 'volumes') || latestResult(events, 'volumes');
  const volumesSource = activeStage.type === 'volumes' ? latestResult(events, activeStage.id) : volumesBaselineArtifact;
  const volumesDraft = activeStage.type === 'volumes' ? stageDraftPersistence.draft : undefined;
  const volumesValue = volumesDraft?.source === volumesSource ? volumesDraft.value : volumesSource;
  const detailBaselineArtifact = latestApprovedArtifact(events, 'detail') || latestResult(events, 'detail');
  const detailSource = activeStage.type === 'detail' ? latestResult(events, activeStage.id) : detailBaselineArtifact;
  const detailDraft = activeStage.type === 'detail' ? stageDraftPersistence.draft : undefined;
  const detailValue = detailDraft?.source === detailSource ? detailDraft.value : detailSource;
  const projection = runtimeArtifactProjection({
    activeStageType: activeStage.type,
    brief: briefArtifact,
    cast: castArtifact,
    detail: detailValue,
    events,
    spine: spineValue,
    volumes: volumesValue,
  });

  const insightContext: RuntimeInsightContext = {
    artifactProjection: projection.stage,
    events,
    characterGraphOverride: projection.characterGraph,
    briefWorldbuilding: projection.worldbuilding,
    knowledgeDocuments,
    memoryEvents,
    onOpenKnowledgeManager,
    writebackStatus: projection.writeback,
    contextManifest,
    workflow,
  };

  return (
    <section className={`stage-run-workbench${hasSidePanels ? '' : ' no-side-panels'}${hasContextRail ? ' context-rail-layout' : ''}`}>
      <BriefStageLoadingOverlay events={events} visible={activeStage.type === 'brief' && briefStageLoadingVisible(activeRunId, events)} />
      <StageSettlementOverlay
        dwell={settlementDwell}
        events={events}
        onContinue={onContinueSettlement}
        open={Boolean(settlementStageId)}
        stage={workflow.nodes.find((stage) => stage.id === settlementStageId) ?? activeStage}
      />
      <StageRunMainArea
        activeRunId={activeRunId}
        events={events}
        onApproveBrief={onApproveBrief}
        onConfirmStageArtifact={onConfirmStageArtifact}
        onOpenConsole={onOpenConsole}
        onOpenRuntimePanel={setSideDetailPanel}
        onRegenerateBrief={onRegenerateBrief}
        onRegenerateStageDraft={onRegenerateStageDraft}
        onStageArtifactDraftChange={stageDraftPersistence.change}
        stage={activeStage}
        stageArtifactDraft={stageDraftPersistence.draft}
        stageArtifactDraftError={stageDraftPersistence.error}
        stageArtifactDraftStatus={stageDraftPersistence.status}
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
