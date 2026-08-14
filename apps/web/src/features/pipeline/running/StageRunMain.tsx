import { BookOpenText, PanelLeftOpen } from 'lucide-react';
import type { GraphRunDefinition, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import { StageDecisionControls } from './StageDecisionControls';
import { CharacterStageView } from './CharacterStageView';
import { StoryBriefStageView } from './StoryBriefStageView';
import { StageArtifactFrame } from './StageArtifactFrame';
import { SpineStageView } from './SpineStageView';
import { VolumeStageView } from './VolumeStageView';
import { DetailStageViewVnext } from './DetailStageViewVnext';
import { ChapterStageViewVnext } from './ChapterStageViewVnext';
import { CoverStageViewVnext } from './CoverStageViewVnext';
import { ExportStageViewVnext } from './ExportStageViewVnext';
import {
  characterBibleSemanticReadiness,
  coverSemanticReadiness,
  detailSemanticReadiness,
  spineSemanticReadiness,
  volumeSemanticReadiness,
} from './artifactSemanticReadiness';
import { isStageEvent, latestApprovedArtifact, latestResult, stageConfig, statusText } from './stageRunUtils';
import { ArtifactFixtureNotice, StageArtifactStatePanel } from './StageArtifactStatePanel';
import { currentStageArtifact, stageArtifactState, type StageArtifactDraft } from './stageArtifactState';
import { parseCharacterBibleArtifact } from './characterBibleArtifact';
import { artifactReadiness, parseSpineArtifact, parseDetailArtifact, parseChapterArtifact, parseCoverArtifact, parseExportArtifact, parseVolumesArtifact } from './artifactsVnext';
import { latestProviderUsage } from './runtimeProviderUsage';

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
  const artifactState = stageArtifactState(stage, events, stage.type === 'brief' ? approvalDraft || result : '');
  const sourceArtifactResult = artifactState.status === 'ready' ? artifactState.result : '';
  const artifactResult = currentStageArtifact(sourceArtifactResult, stageArtifactDraft);
  const chapterArtifact = stage.type === 'text' ? parseChapterArtifact(artifactResult).artifact : null;
  const characterResult = latestApprovedArtifact(events, 'cast');
  const characterBible = parseCharacterBibleArtifact(characterResult).artifact;
  const characters = characterBible?.subjects.map(({ id, name }) => ({ id, name })) ?? [];
  const totalChapters = runDefinition?.scale_profile.chapter_target_soft ?? undefined;
  const committedSpine = parseSpineArtifact(latestApprovedArtifact(events, 'spine')).artifact;
  const semanticContext = {
    characterBible,
    spine: committedSpine,
  };
  const isCompleted = events.some((event) => isStageEvent(event, stage.id) && ['artifact.candidate_ready', 'artifact.committed', 'node.completed'].includes(event.type));
  const stageConfirmed = events.some((event) => (
    isStageEvent(event, stage.id)
    && event.type === 'artifact.committed'
    && (stage.type !== 'text' || event.chapter_id === chapterArtifact?.chapter_id)
  ));
  const showArtifact = artifactState.status === 'ready' || (stage.type === 'text' && artifactState.status === 'streaming');
  const spineStatus = stage.type === 'spine' ? spineSemanticReadiness(parseSpineArtifact(artifactResult)) : null;
  const characterStatus = stage.type === 'cast'
    ? characterBibleSemanticReadiness(parseCharacterBibleArtifact(artifactResult).artifact)
    : null;
  const volumeStatus = stage.type === 'volumes' ? volumeSemanticReadiness(parseVolumesArtifact(artifactResult), semanticContext) : null;
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
      <div className="stage-run-artifact-scroll" data-scroll-region="artifact">
      {stage.type === 'brief' ? null : (
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
      <StageArtifactFrame stageLabel={stageDisplayLabel} stageType={stage.type} />
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
      {showArtifact && stage.type === 'brief' ? <StoryBriefStageView onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'cast' ? (
        <CharacterStageView
          onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))}
          readOnly={stageConfirmed}
          result={artifactResult}
          sourceResult={sourceArtifactResult}
          totalChapters={totalChapters}
        />
      ) : null}
      {showArtifact && stage.type === 'spine' ? <SpineStageView onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'volumes' ? <VolumeStageView characters={characters} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} spineTurns={committedSpine?.turns ?? []} /> : null}
      {showArtifact && stage.type === 'detail' ? <DetailStageViewVnext characters={characters} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'text' ? <ChapterStageViewVnext onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'cover' ? <CoverStageViewVnext onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} runId={activeRunId} sourceResult={sourceArtifactResult} /> : null}
      {showArtifact && stage.type === 'export' ? <ExportStageViewVnext deliveryRevision={events.find((event) => event.stage_id === 'export' && event.type === 'artifact.committed')?.event_id ?? ''} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} runId={activeRunId} /> : null}
      {(characterStatus ?? spineStatus ?? volumeStatus ?? detailStatus ?? coverStatus)?.missingLabels.length ? (
        <div className="vnext-contract-warning" role="alert">
          {(characterStatus ?? spineStatus ?? volumeStatus ?? detailStatus ?? coverStatus)?.missingLabels.join('、')}
        </div>
      ) : null}
      {!['brief', 'cast', 'spine', 'volumes', 'detail', 'text', 'cover', 'export'].includes(stage.type) ? (
        <section className="stage-run-card"><BookOpenText size={16} />暂未定义该阶段展示。</section>
      ) : null}
      </div>
      {artifactState.status === 'ready' && stage.type !== 'brief' ? (
        <StageDecisionControls
          completed={isCompleted}
          events={events}
          artifactMissingLabels={characterStatus?.missingLabels ?? spineStatus?.missingLabels ?? volumeStatus?.missingLabels ?? detailStatus?.missingLabels ?? writingStatus?.missingLabels ?? coverStatus?.missingLabels ?? exportStatus?.missingLabels ?? []}
          artifactReady={characterStatus?.ready ?? spineStatus?.ready ?? volumeStatus?.ready ?? detailStatus?.ready ?? writingStatus?.ready ?? coverStatus?.ready ?? exportStatus?.ready ?? true}
          onConfirmStageArtifact={(stageId) => onConfirmStageArtifact(stageId, artifactResult)}
          onRegenerateStageDraft={onRegenerateStageDraft}
          chapterId={chapterArtifact?.chapter_id ?? ''}
          stage={stage}
          workflow={workflow}
        />
      ) : null}
      {artifactState.status === 'ready' && stage.type === 'brief' ? (
        <StageDecisionControls
          completed={isCompleted}
          events={events}
          artifactReady
          onConfirmStageArtifact={() => onApproveBrief(artifactResult)}
          onRegenerateStageDraft={(_, direction) => { void onRegenerateBrief(direction); }}
          stage={stage}
          workflow={workflow}
        />
      ) : null}
    </>
  );
}
