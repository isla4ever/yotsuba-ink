import { BookOpenText, PanelLeftOpen } from 'lucide-react';
import type { GraphRunDefinition, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import { StageDecisionControls } from './StageDecisionControls';
import { CharacterStageView } from './CharacterStageView';
import { StoryBriefStageView } from './StoryBriefStageView';
import { SummaryStageViewVnext } from './SummaryStageViewVnext';
import { OutlineStageViewVnext } from './OutlineStageViewVnext';
import { DetailStageViewVnext } from './DetailStageViewVnext';
import { ChapterStageViewVnext } from './ChapterStageViewVnext';
import { CoverStageViewVnext } from './CoverStageViewVnext';
import { ExportStageViewVnext } from './ExportStageViewVnext';
import {
  characterBibleSemanticReadiness,
  coverSemanticReadiness,
  detailSemanticReadiness,
  outlineSemanticReadiness,
  summarySemanticReadiness,
} from './artifactSemanticReadiness';
import { isStageEvent, latestApprovedArtifact, latestResult, stageConfig, statusText } from './stageRunUtils';
import { ArtifactFixtureNotice, StageArtifactStatePanel } from './StageArtifactStatePanel';
import { currentStageArtifact, stageArtifactState, type StageArtifactDraft } from './stageArtifactState';
import { parseCharacterBibleArtifact } from './characterBibleArtifact';
import { artifactReadiness, parseStoryBriefArtifact, parseSummaryArtifact, parseOutlineArtifact, parseDetailArtifact, parseChapterArtifact, parseCoverArtifact, parseExportArtifact } from './artifactsVnext';
import { latestProviderUsage } from './runtimeProviderUsage';
import { buildDetailObligationOptions, detailObligationRefIds } from './detailObligationRegistry';

type Props = {
  activeRunId: string;
  approvalDraft: string;
  approvalPending: boolean;
  events: RunEvent[];
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onOpenWorkbench?: () => void;
  onOpenRuntimePanel: (panel: 'character' | 'worldbuilding') => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
  onConfirmStageArtifact: (stageId: string, artifact?: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
  onStageArtifactDraftChange: (stageId: string, source: string, value: string) => void;
  stageArtifactDraft?: StageArtifactDraft;
  runDefinition: GraphRunDefinition | null;
  stage: WorkflowStage;
  workflow: WorkflowDefinition;
};

export function StageRunMain({
  activeRunId,
  approvalDraft,
  approvalPending,
  events,
  onApprovalDraftChange,
  onApproveBrief,
  onOpenWorkbench,
  onOpenRuntimePanel,
  onRegenerateBrief,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  onStageArtifactDraftChange,
  stageArtifactDraft,
  runDefinition,
  stage,
  workflow,
}: Props) {
  const config = stageConfig(stage.type);
  const stageDisplayLabel = stage.label;
  const result = latestResult(events, stage.id);
  const artifactState = stageArtifactState(stage, events, stage.type === 'info' ? approvalDraft || result : '');
  const sourceArtifactResult = artifactState.status === 'ready' ? artifactState.result : '';
  const artifactResult = currentStageArtifact(sourceArtifactResult, stageArtifactDraft);
  const chapterArtifact = stage.type === 'text' ? parseChapterArtifact(artifactResult).artifact : null;
  const characterResult = latestApprovedArtifact(events, 'characters');
  const characterBible = parseCharacterBibleArtifact(characterResult).artifact;
  const characters = characterBible?.characters.map(({ id, name }) => ({ id, name })) ?? [];
  const totalChapters = runDefinition?.book_scale_plan.total_chapters;
  const volumeWindows = runDefinition?.book_scale_plan.volumes.map((volume) => (
    volume.chapter_start === volume.chapter_end
      ? `chapter:${volume.chapter_start}`
      : `chapter:${volume.chapter_start}-${volume.chapter_end}`
  )) ?? [];
  const storyBrief = parseStoryBriefArtifact(latestApprovedArtifact(events, 'info')).artifact;
  const committedOutline = parseOutlineArtifact(latestApprovedArtifact(events, 'outline')).artifact;
  const obligationOptions = buildDetailObligationOptions(storyBrief, characterBible, committedOutline);
  const semanticContext = {
    characterBible,
    obligationRefIds: detailObligationRefIds(obligationOptions),
    requireFrozenScale: Boolean(activeRunId) && !runDefinition,
    totalChapters,
  };
  const isCompleted = events.some((event) => isStageEvent(event, stage.id) && ['artifact.candidate_ready', 'artifact.committed', 'node.completed'].includes(event.type));
  const stageConfirmed = events.some((event) => (
    isStageEvent(event, stage.id)
    && event.type === 'artifact.committed'
    && (stage.type !== 'text' || event.chapter_id === chapterArtifact?.chapter_id)
  ));
  const showArtifact = artifactState.status === 'ready' || (stage.type === 'text' && artifactState.status === 'streaming');
  const summaryStatus = stage.type === 'summary' ? summarySemanticReadiness(parseSummaryArtifact(artifactResult), semanticContext) : null;
  const characterStatus = stage.type === 'characters'
    ? characterBibleSemanticReadiness(parseCharacterBibleArtifact(artifactResult).artifact, semanticContext)
    : null;
  const outlineStatus = stage.type === 'outline' ? outlineSemanticReadiness(parseOutlineArtifact(artifactResult), semanticContext) : null;
  const detailStatus = stage.type === 'detail' ? detailSemanticReadiness(parseDetailArtifact(artifactResult), semanticContext) : null;
  const writingStatus = stage.type === 'text' ? artifactReadiness(parseChapterArtifact(artifactResult)) : null;
  const coverStatus = stage.type === 'cover' ? coverSemanticReadiness(parseCoverArtifact(artifactResult), {
    ...semanticContext,
    coverAssetIds: new Set(events.filter((event) => event.type === 'cover.asset_ready').map((event) => event.payload_ref).filter(Boolean)),
  }) : null;
  const exportStatus = stage.type === 'export' ? artifactReadiness(parseExportArtifact(artifactResult)) : null;
  const providerUsage = latestProviderUsage(events);
  return (
    <>
      {stage.type === 'info' ? null : (
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
            {providerUsage.provider_operations ? (
              <span>{providerUsage.provider_operations} 次调用 · {providerUsage.total_tokens.toLocaleString()} tokens</span>
            ) : null}
          </div>
        </div>
      )}
      {artifactState.status === 'ready' && artifactState.source === 'fixture' ? <ArtifactFixtureNotice /> : null}
      {!showArtifact ? (
        <StageArtifactStatePanel
          label={stageDisplayLabel}
          onReturn={onOpenWorkbench}
          runStarted={Boolean(activeRunId) || events.some((event) => event.type === 'run.started')}
          stageType={stage.type}
          state={artifactState}
        />
      ) : null}
      {showArtifact && stage.type === 'info' ? <StoryBriefStageView onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'characters' ? (
        <CharacterStageView
          onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))}
          readOnly={stageConfirmed}
          result={artifactResult}
          sourceResult={sourceArtifactResult}
          totalChapters={totalChapters}
        />
      ) : null}
      {showArtifact && stage.type === 'summary' ? <SummaryStageViewVnext characters={characters} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'outline' ? <OutlineStageViewVnext characters={characters} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} volumeWindows={volumeWindows} /> : null}
      {showArtifact && stage.type === 'detail' ? <DetailStageViewVnext characters={characters} obligationOptions={obligationOptions} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'text' ? <ChapterStageViewVnext onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'cover' ? <CoverStageViewVnext onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} runId={activeRunId} sourceResult={sourceArtifactResult} /> : null}
      {showArtifact && stage.type === 'export' ? <ExportStageViewVnext deliveryRevision={events.find((event) => event.stage_id === 'export' && event.type === 'artifact.committed')?.event_id ?? ''} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} runId={activeRunId} /> : null}
      {(characterStatus ?? summaryStatus ?? outlineStatus ?? detailStatus ?? coverStatus)?.missingLabels.length ? (
        <div className="vnext-contract-warning" role="alert">
          {(characterStatus ?? summaryStatus ?? outlineStatus ?? detailStatus ?? coverStatus)?.missingLabels.join('、')}
        </div>
      ) : null}
      {!['info', 'characters', 'summary', 'outline', 'detail', 'text', 'cover', 'export'].includes(stage.type) ? (
        <section className="stage-run-card"><BookOpenText size={16} />暂未定义该阶段展示。</section>
      ) : null}
      {artifactState.status === 'ready' && stage.type !== 'info' ? (
        <StageDecisionControls
          completed={isCompleted}
          events={events}
          artifactMissingLabels={characterStatus?.missingLabels ?? summaryStatus?.missingLabels ?? outlineStatus?.missingLabels ?? detailStatus?.missingLabels ?? writingStatus?.missingLabels ?? coverStatus?.missingLabels ?? exportStatus?.missingLabels ?? []}
          artifactReady={characterStatus?.ready ?? summaryStatus?.ready ?? outlineStatus?.ready ?? detailStatus?.ready ?? writingStatus?.ready ?? coverStatus?.ready ?? exportStatus?.ready ?? true}
          onConfirmStageArtifact={(stageId) => onConfirmStageArtifact(stageId, artifactResult)}
          onRegenerateStageDraft={onRegenerateStageDraft}
          chapterId={chapterArtifact?.chapter_id ?? ''}
          stage={stage}
          workflow={workflow}
        />
      ) : null}
    </>
  );
}
