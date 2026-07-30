import { BookOpenText, PanelLeftOpen } from 'lucide-react';
import type { ChapterQualityRepairTarget, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import { InfoRecommendationView } from './InfoRecommendationView';
import { BalancedVariantFocus, StageDecisionControls } from './StageDecisionControls';
import { StageCandidateCompare } from './StageCandidateCompare';
import { CoverStageView } from './CoverStageView';
import { ExportStageView } from './ExportStageView';
import { DetailStageView } from './DetailStageView';
import { OutlineStageView } from './OutlineStageView';
import { SummaryStageView } from './SummaryStageView';
import { WritingStageView } from './WritingStageView';
import { latestApprovedArtifact, latestResult, stageConfig, stageQualityScore, statusText, streamDeltasFor } from './stageRunUtils';
import { ArtifactFixtureNotice, StageArtifactStatePanel } from './StageArtifactStatePanel';
import { currentStageArtifact, stageArtifactState, type StageArtifactDraft } from './stageArtifactState';
import { coverArtifact, detailArtifact, outlineArtifact, summaryArtifact } from './stageArtifacts';
import { outlineBaseline, outlineReadiness } from './outlineArtifactModel';
import { summaryInfoBaseline, summaryReadiness } from './summaryArtifactModel';
import { detailBaseline, detailReadiness } from './detailArtifactModel';
import { writingArtifact, writingReadiness } from './writingArtifactModel';
import { latestDraftRegenerationFailure } from './stageRunFocus';
import { coverReadiness } from './coverPresentation';
import { infoArtifactSource } from './infoArtifactSource';

type Props = {
  activeRunId: string;
  approvalDraft: string;
  approvalPending: boolean;
  events: RunEvent[];
  memoryEvents: RunEvent[];
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onEditInfoCharacter?: () => void;
  onEditInfoWorldbuilding?: () => void;
  onOpenWorkbench?: () => void;
  onOpenRuntimePanel: (panel: 'character' | 'worldbuilding') => void;
  onQualityRepairHandled: () => void;
  onRepairQualityFinding: (target: ChapterQualityRepairTarget) => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
  onConfirmStageArtifact: (stageId: string, artifact?: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string) => void;
  onRequestVariantCompare: (stageId: string) => void;
  onSelectBalancedVariant: (stageId: string, variantId: string, modelPicked?: boolean) => void;
  onSelectDraftCandidate: (stageId: string, candidateKey: string) => void;
  onSelectedWritingChapter: (chapterId: string) => void;
  onStageArtifactDraftChange: (stageId: string, source: string, value: string) => void;
  stageArtifactDraft?: StageArtifactDraft;
  qualityRepairTarget: ChapterQualityRepairTarget | null;
  stage: WorkflowStage;
  compareFocus: boolean;
  draftFocus: boolean;
  workflow: WorkflowDefinition;
};

export function StageRunMain({
  activeRunId,
  approvalDraft,
  approvalPending,
  events,
  memoryEvents,
  onApprovalDraftChange,
  onApproveBrief,
  onEditInfoCharacter,
  onEditInfoWorldbuilding,
  onOpenWorkbench,
  onOpenRuntimePanel,
  onQualityRepairHandled,
  onRepairQualityFinding,
  onRegenerateBrief,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  onRequestVariantCompare,
  onSelectBalancedVariant,
  onSelectDraftCandidate,
  onSelectedWritingChapter,
  onStageArtifactDraftChange,
  stageArtifactDraft,
  qualityRepairTarget,
  stage,
  compareFocus,
  draftFocus,
  workflow,
}: Props) {
  const config = stageConfig(stage.type);
  const stageDisplayLabel = stage.type === 'info_recommend' ? '小说信息推荐' : stage.label;
  const result = latestResult(events, stage.id);
  const infoSource = infoArtifactSource(events, approvalDraft, approvalPending);
  const artifactState = stageArtifactState(stage, events, stage.type === 'info_recommend' ? infoSource || result : '');
  const sourceArtifactResult = artifactState.status === 'ready' ? artifactState.result : '';
  const artifactResult = currentStageArtifact(sourceArtifactResult, stageArtifactDraft);
  const infoBaseline = infoArtifactSource(events, approvalDraft, stage.type === 'info_recommend' && approvalPending);
  const summaryBaseline = latestApprovedArtifact(events, 'summary') || latestResult(events, 'summary');
  const outlineBaselineArtifact = latestApprovedArtifact(events, 'outline') || latestResult(events, 'outline');
  const streamDeltas = streamDeltasFor(events, stage.id);
  const isCompleted = events.some((event) => event.type === 'node_completed' && event.node_id === stage.id);
  const stageConfirmed = events.some((event) => event.type === 'stage_artifact_confirmed' && event.node_id === stage.id);
  const showArtifact = artifactState.status === 'ready' || (stage.type === 'chapter_text' && artifactState.status === 'streaming');
  const summaryStatus = stage.type === 'summary'
    ? summaryReadiness(summaryArtifact(artifactResult), summaryInfoBaseline(infoBaseline).characters.map((character) => character.name))
    : null;
  const outlineStatus = stage.type === 'outline'
    ? outlineReadiness(outlineArtifact(artifactResult), outlineBaseline(infoBaseline, summaryBaseline))
    : null;
  const detailContext = detailBaseline(infoBaseline, outlineBaselineArtifact);
  const detailStatus = stage.type === 'detail_outline'
    ? detailReadiness(detailArtifact(artifactResult), detailContext)
    : null;
  const writingStatus = stage.type === 'chapter_text'
    ? writingReadiness(writingArtifact(artifactResult, events))
    : null;
  const coverStatus = stage.type === 'cover_image'
    ? coverReadiness(coverArtifact(artifactResult))
    : null;
  const qualityScore = stageQualityScore(events, stage.id);
  const infoRegenerationFailure = stage.type === 'info_recommend'
    ? latestDraftRegenerationFailure(stage.id, events)
    : null;
  if (compareFocus) return <BalancedVariantFocus events={events} onSelectBalancedVariant={onSelectBalancedVariant} stage={stage} />;
  if (draftFocus) return <StageCandidateCompare events={events} mode={workflow.quality_mode} onSelectDraftCandidate={onSelectDraftCandidate} stage={stage} />;
  return (
    <>
      {stage.type === 'info_recommend' ? null : (
        <div className="stage-run-head">
          <div>
            <p className="eyebrow">阶段工作台</p>
            <h2>{config.icon}{stageDisplayLabel}</h2>
          </div>
          <div className="writing-metrics">
            {onOpenWorkbench ? (
              <button className="stage-workbench-return" onClick={onOpenWorkbench} title="返回流水线工作台" type="button">
                <PanelLeftOpen size={14} />
              </button>
            ) : null}
            <span>{qualityModeProfiles[workflow.quality_mode].title}</span>
            <span>{statusText(stage, events)}</span>
            <span title={qualityScore == null ? '当前阶段质量阈值' : '质量检查评分'}>
              {qualityScore == null ? `阈值 ${stage.quality_policy.min_score.toFixed(2)}` : `Q ${qualityScore.toFixed(2)}`}
            </span>
          </div>
        </div>
      )}
      {artifactState.status === 'ready' && artifactState.source === 'fixture' ? <ArtifactFixtureNotice /> : null}
      {!showArtifact ? (
        <StageArtifactStatePanel
          label={stageDisplayLabel}
          onReturn={onOpenWorkbench}
          runStarted={Boolean(activeRunId) || events.some((event) => event.type === 'run_started')}
          stageType={stage.type}
          state={artifactState}
        />
      ) : null}
      {showArtifact && stage.type === 'info_recommend' ? (
        <InfoRecommendationView
          approvalDraft={infoSource || artifactResult}
          approvalPending={approvalPending}
          qualityMode={workflow.quality_mode}
          regenerationFailed={Boolean(infoRegenerationFailure)}
          stage={stage}
          onApprovalDraftChange={onApprovalDraftChange}
          onApproveBrief={onApproveBrief}
          onEditCharacter={onEditInfoCharacter ?? (() => undefined)}
          onEditWorldbuilding={onEditInfoWorldbuilding ?? (() => undefined)}
          onRegenerateBrief={onRegenerateBrief}
        />
      ) : null}
      {showArtifact && stage.type === 'summary' ? (
        <SummaryStageView
          baseline={infoBaseline}
          deltas={streamDeltas}
          generating={!isCompleted}
          onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))}
          qualityMode={workflow.quality_mode}
          readOnly={stageConfirmed}
          result={artifactResult}
          sourceResult={sourceArtifactResult}
        />
      ) : null}
      {showArtifact && stage.type === 'outline' ? (
        <OutlineStageView
          baseline={outlineBaseline(infoBaseline, summaryBaseline)}
          deltas={streamDeltas}
          generating={!isCompleted}
          onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))}
          readiness={outlineStatus ?? { completed: 0, missingLabels: [], ready: false, total: 0 }}
          readOnly={stageConfirmed}
          result={artifactResult}
          sourceResult={sourceArtifactResult}
        />
      ) : null}
      {showArtifact && stage.type === 'detail_outline' ? (
        <DetailStageView
          baseline={detailContext}
          deltas={streamDeltas}
          generating={!isCompleted}
          onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))}
          readiness={detailStatus ?? { completed: 0, missingLabels: [], ready: false, total: 0 }}
          readOnly={stageConfirmed}
          result={artifactResult}
          sourceResult={sourceArtifactResult}
        />
      ) : null}
      {showArtifact && stage.type === 'chapter_text' ? (
        <WritingStageView
          activeRunId={activeRunId}
          dirty={Boolean(stageArtifactDraft && stageArtifactDraft.source === sourceArtifactResult)}
          events={events}
          memoryEvents={memoryEvents}
          onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))}
          onOpenRuntimePanel={onOpenRuntimePanel}
          onQualityRepairHandled={onQualityRepairHandled}
          onRepairQualityFinding={onRepairQualityFinding}
          onSelectedChapterChange={onSelectedWritingChapter}
          qualityRepairTarget={qualityRepairTarget}
          readOnly={stageConfirmed}
          result={artifactResult}
          sourceResult={sourceArtifactResult}
          stageId={stage.id}
          workflow={workflow}
        />
      ) : null}
      {showArtifact && stage.type === 'cover_image' ? <CoverStageView activeRunId={activeRunId} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'export_artifact' ? <ExportStageView activeRunId={activeRunId} result={artifactResult} /> : null}
      {!['info_recommend', 'summary', 'outline', 'detail_outline', 'chapter_text', 'cover_image', 'export_artifact'].includes(stage.type) ? (
        <section className="stage-run-card"><BookOpenText size={16} />暂未定义该阶段展示。</section>
      ) : null}
      {artifactState.status === 'ready' && !['info_recommend', 'export_artifact'].includes(stage.type) ? (
        <StageDecisionControls
          completed={isCompleted}
          events={events}
          artifactMissingLabels={summaryStatus?.missingLabels ?? outlineStatus?.missingLabels ?? detailStatus?.missingLabels ?? writingStatus?.missingLabels ?? coverStatus?.missingLabels ?? []}
          artifactReady={summaryStatus?.ready ?? outlineStatus?.ready ?? detailStatus?.ready ?? writingStatus?.ready ?? coverStatus?.ready ?? true}
          onConfirmStageArtifact={(stageId) => onConfirmStageArtifact(stageId, artifactResult)}
          onRegenerateStageDraft={onRegenerateStageDraft}
          onRequestVariantCompare={onRequestVariantCompare}
          stage={stage}
          workflow={workflow}
        />
      ) : null}
    </>
  );
}
