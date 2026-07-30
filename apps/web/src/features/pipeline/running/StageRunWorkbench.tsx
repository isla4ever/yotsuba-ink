import { AnimatePresence } from 'motion/react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ChapterQualityRepairTarget, KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { LoadingOverlay } from '../layout/LoadingOverlay';
import { worldbuildingFromDraft } from '../lib/stageConfig';
import { InfoArtifactEditor } from './InfoArtifactEditor';
import { InfoStageLoadingOverlay } from './InfoStageLoadingOverlay';
import { infoStageLoadingVisible } from './infoStageLoadingState';
import { RuntimeInsights } from './RuntimeInsights';
import { type RuntimeInsightContext, type RuntimeWritebacks } from './RuntimeInsightPanel';
import { RuntimeSideDetailSheet } from './RuntimeSideDetailSheet';
import { StageRunMainArea } from './StageRunMainArea';
import { currentStageArtifact, stageArtifactState, type StageArtifactDraft } from './stageArtifactState';
import { StageSettlementOverlay } from './StageSettlementOverlay';
import {
  graphFromRecommendation,
  normalizeRecommendation,
  recommendationGraphSignature,
  type InfoEditorTarget,
  type InfoRecommendation,
} from './infoRecommendationModel';
import { shouldFocusDraftCandidates, shouldFocusVariants } from './stageRunFocus';
import { stageRuntimeLayout, type RuntimePanelKey } from './stageRuntimeLayout';
import { latestApprovedArtifact, latestResult } from './stageRunUtils';
import { detailArtifact, outlineArtifact, summaryArtifact } from './stageArtifacts';
import { graphWithSummaryArcs, summaryWritebackDetail } from './summaryArtifactModel';
import { graphWithOutlineProgressions, outlineWritebackSummary } from './outlineArtifactModel';
import { detailWritebackSummary, graphWithDetailShifts } from './detailArtifactModel';
import { chapterReviewInsight, writingArtifact } from './writingArtifactModel';
import { infoArtifactSource } from './infoArtifactSource';

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
  onRegenerateStageDraft: (stageId: string, direction: string) => void;
  onRequestVariantCompare: (stageId: string) => void;
  onSelectBalancedVariant: (stageId: string, variantId: string, modelPicked?: boolean) => void;
  onSelectDraftCandidate: (stageId: string, candidateKey: string) => void;
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
  onRequestVariantCompare,
  onSelectBalancedVariant,
  onSelectDraftCandidate,
  workflow,
  activeStage,
  settlementDwell,
  settlementStageId,
}: Props) {
  const [stageArtifactDrafts, setStageArtifactDrafts] = useState<Record<string, StageArtifactDraft>>({});
  const [editor, setEditor] = useState<InfoEditorTarget | null>(null);
  const [sideDetailPanel, setSideDetailPanel] = useState<RuntimePanelKey | null>(null);
  const [qualityRepairTarget, setQualityRepairTarget] = useState<ChapterQualityRepairTarget | null>(null);
  const [selectedWritingChapterId, setSelectedWritingChapterId] = useState('');
  const runtimeLayout = stageRuntimeLayout[activeStage.type];
  const variantFocus = shouldFocusVariants(activeStage, events, workflow);
  const draftFocus = shouldFocusDraftCandidates(activeStage, events, workflow);
  const focusMode = variantFocus || draftFocus;
  const hasSidePanels = !focusMode && (runtimeLayout.primary.length > 0 || runtimeLayout.compact.length > 0);
  const hasContextRail = hasSidePanels && runtimeLayout.primary.length === 0 && runtimeLayout.compact.length > 0;
  const variantJudging = variantFocus && events.some((event) => event.type === 'variant_judged' && event.node_id === activeStage.id);
  const infoStage = workflow.nodes.find((stage) => stage.type === 'info_recommend') ?? activeStage;
  const infoBaselineArtifact = latestApprovedArtifact(events, 'info') || latestResult(events, 'info') || approvalDraft;
  const activeInfoArtifact = infoArtifactSource(events, approvalDraft, approvalPending);
  const infoRecommendation = normalizeRecommendation(activeStage.type === 'info_recommend' ? activeInfoArtifact : infoBaselineArtifact, infoStage);
  const infoArtifactConfirmed = events.some((event) => event.type === 'stage_artifact_confirmed' && event.node_id === 'info')
    || (!approvalPending && activeStage.type === 'info_recommend');
  const infoArtifactStatus = activeStage.type === 'info_recommend'
    ? (infoArtifactConfirmed ? 'confirmed' as const : 'draft' as const)
    : undefined;
  const infoWorldbuilding = worldbuildingFromDraft(infoRecommendation.worldbuilding_detail);
  const characterGraphSignature = recommendationGraphSignature(infoRecommendation);
  const baseInfoCharacterGraph = useMemo(
    () => graphFromRecommendation(infoRecommendation),
    [characterGraphSignature],
  );
  const summaryBaselineArtifact = latestApprovedArtifact(events, 'summary') || latestResult(events, 'summary');
  const summarySource = activeStage.type === 'summary' ? latestResult(events, activeStage.id) : summaryBaselineArtifact;
  const summaryDraft = stageArtifactDrafts[activeStage.id];
  const summaryValue = summaryDraft?.source === summarySource ? summaryDraft.value : summarySource;
  const summaryCurrentArtifact = summaryArtifact(summaryValue);
  const outlineBaselineArtifact = latestApprovedArtifact(events, 'outline') || latestResult(events, 'outline');
  const outlineSource = activeStage.type === 'outline' ? latestResult(events, activeStage.id) : outlineBaselineArtifact;
  const outlineDraft = stageArtifactDrafts[activeStage.id];
  const outlineValue = outlineDraft?.source === outlineSource ? outlineDraft.value : outlineSource;
  const outlineCurrentArtifact = outlineArtifact(outlineValue);
  const detailSource = activeStage.type === 'detail_outline' ? latestResult(events, activeStage.id) : '';
  const detailDraft = stageArtifactDrafts[activeStage.id];
  const detailValue = detailDraft?.source === detailSource ? detailDraft.value : detailSource;
  const detailCurrentArtifact = detailArtifact(detailValue);
  const textState = activeStage.type === 'chapter_text' ? stageArtifactState(activeStage, events) : { status: 'empty' as const };
  const textSource = textState.status === 'ready' ? textState.result : '';
  const textValue = currentStageArtifact(textSource, stageArtifactDrafts[activeStage.id]);
  const textArtifact = activeStage.type === 'chapter_text' ? writingArtifact(textValue, events) : undefined;
  const chapterReview = textArtifact
    ? chapterReviewInsight(textArtifact, selectedWritingChapterId)
    : undefined;
  const summaryGraph = graphWithSummaryArcs(baseInfoCharacterGraph, summaryArtifact(summaryBaselineArtifact));
  const outlineGraph = graphWithOutlineProgressions(summaryGraph, outlineCurrentArtifact);
  const characterGraphOverride = activeStage.type === 'info_recommend'
    ? baseInfoCharacterGraph
    : activeStage.type === 'summary'
      ? graphWithSummaryArcs(baseInfoCharacterGraph, summaryCurrentArtifact)
      : activeStage.type === 'outline'
        ? outlineGraph
        : activeStage.type === 'detail_outline'
          ? graphWithDetailShifts(outlineGraph, detailCurrentArtifact)
          : undefined;
  const summaryWritebacks: RuntimeWritebacks = activeStage.type === 'summary'
    ? { character: summaryWritebackDetail(summaryCurrentArtifact) }
    : {};
  const outlineWritebacks: RuntimeWritebacks = activeStage.type === 'outline'
    ? outlineWritebackSummary(outlineCurrentArtifact)
    : {};
  const detailWritebacks: RuntimeWritebacks = activeStage.type === 'detail_outline'
    ? detailWritebackSummary(detailCurrentArtifact)
    : {};
  const stageConfirmed = events.some((event) => event.type === 'stage_artifact_confirmed' && event.node_id === activeStage.id);

  useEffect(() => {
    setQualityRepairTarget(null);
    if (activeStage.type !== 'chapter_text') setSelectedWritingChapterId('');
  }, [activeStage.id, activeStage.type]);

  const repairQualityFinding = useCallback((target: ChapterQualityRepairTarget) => {
    setQualityRepairTarget(target);
    setSideDetailPanel(null);
  }, []);
  const clearQualityRepair = useCallback(() => setQualityRepairTarget(null), []);

  const updateInfoDraft = (patch: Partial<InfoRecommendation>) => {
    onApprovalDraftChange(JSON.stringify({ ...infoRecommendation, ...patch }, null, 2));
  };

  const insightContext: RuntimeInsightContext = {
    chapterReview,
    detailWritebacks,
    events,
    characterGraphOverride,
    infoWorldbuilding,
    infoArtifactStatus,
    knowledgeDocuments,
    memoryEvents,
    onOpenKnowledgeManager,
    onRepairQualityFinding: activeStage.type === 'chapter_text' && !stageConfirmed ? repairQualityFinding : undefined,
    outlineWritebacks,
    summaryWritebacks,
    workflow,
  };

  return (
    <section className={`stage-run-workbench${hasSidePanels ? '' : ' no-side-panels'}${hasContextRail ? ' context-rail-layout' : ''}`}>
      <InfoStageLoadingOverlay events={events} visible={activeStage.type === 'info_recommend' && infoStageLoadingVisible(activeRunId, events)} />
      <StageSettlementOverlay
        dwell={settlementDwell}
        events={events}
        onContinue={onContinueSettlement}
        open={Boolean(settlementStageId)}
        stage={workflow.nodes.find((stage) => stage.id === settlementStageId) ?? activeStage}
      />
      <LoadingOverlay
        className="variant-judging-overlay"
        detail="质量检查正在衡量连续性、人物一致性、伏笔推进与语言质感，完成后会选出最佳版本。"
        eyebrow="候选择优"
        open={variantJudging}
        title="正在进行候选版本比对"
      />
      <StageRunMainArea
        activeRunId={activeRunId}
        approvalDraft={approvalDraft}
        approvalPending={approvalPending}
        compareFocus={variantFocus}
        draftFocus={draftFocus}
        events={events}
        memoryEvents={memoryEvents}
        focusMode={focusMode}
        onApprovalDraftChange={onApprovalDraftChange}
        onApproveBrief={onApproveBrief}
        onConfirmStageArtifact={onConfirmStageArtifact}
        onEditInfoCharacter={() => setEditor('character')}
        onEditInfoWorldbuilding={() => setEditor('worldbuilding')}
        onOpenWorkbench={onOpenWorkbench}
        onOpenRuntimePanel={setSideDetailPanel}
        onQualityRepairHandled={clearQualityRepair}
        onRepairQualityFinding={repairQualityFinding}
        onRegenerateBrief={onRegenerateBrief}
        onRegenerateStageDraft={onRegenerateStageDraft}
        onRequestVariantCompare={onRequestVariantCompare}
        onSelectBalancedVariant={onSelectBalancedVariant}
        onSelectDraftCandidate={onSelectDraftCandidate}
        onSelectedWritingChapter={setSelectedWritingChapterId}
        onStageArtifactDraftChange={(stageId, source, value) => {
          setStageArtifactDrafts((current) => ({ ...current, [stageId]: { source, value } }));
        }}
        stage={activeStage}
        stageArtifactDraft={stageArtifactDrafts[activeStage.id]}
        qualityRepairTarget={qualityRepairTarget}
        workflow={workflow}
      />
      <RuntimeInsights
        {...insightContext}
        activeStage={activeStage}
        compactPanelKeys={runtimeLayout.compact}
        panelKeys={runtimeLayout.primary}
        visible={hasSidePanels}
        onEditInfo={setEditor}
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
      <AnimatePresence>
        {editor ? (
          <InfoArtifactEditor
            key={editor}
            mode={editor}
            qualityMode={workflow.quality_mode}
            readOnly={infoArtifactConfirmed}
            recommendation={infoRecommendation}
            onClose={() => setEditor(null)}
            onSave={(next) => {
              updateInfoDraft(next);
              setEditor(null);
            }}
          />
        ) : null}
      </AnimatePresence>
    </section>
  );
}
