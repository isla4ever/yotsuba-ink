import { BookOpenText, PanelLeftOpen } from 'lucide-react';
import type { GraphRunDefinition, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import { suggestScalePlan } from '../lib/narrativeScale';
import { failureMessageForDecision, isFailureDecision, pendingStageDecision } from '../lib/runDecisionProjection';
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
import { isStageEvent, latestApprovedArtifact, stageConfig, statusText } from './stageRunUtils';
import { ArtifactFixtureNotice, StageArtifactStatePanel } from './StageArtifactStatePanel';
import { currentStageArtifact, stageArtifactState, type StageArtifactDraft } from './stageArtifactState';
import { parseCharacterBibleArtifact } from './characterBibleArtifact';
import { artifactReadiness, parseSpineArtifact, parseDetailArtifact, parseChapterArtifact, parseCoverArtifact, parseExportArtifact, parseVolumesArtifact } from './artifactsVnext';
import { latestProviderUsage } from './runtimeProviderUsage';
import type { StageArtifactDraftSaveStatus } from '../state/useStageArtifactDraft';

type Props = {
  activeRunId: string;
  events: RunEvent[];
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onOpenConsole?: () => void;
  onOpenRuntimePanel: (panel: 'character' | 'worldbuilding') => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
  onConfirmStageArtifact: (stageId: string, artifact?: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
  onStageArtifactDraftChange: (stageId: string, source: string, value: string) => void;
  stageArtifactDraft?: StageArtifactDraft;
  stageArtifactDraftError?: string;
  stageArtifactDraftStatus?: StageArtifactDraftSaveStatus;
  runDefinition: GraphRunDefinition | null;
  stage: WorkflowStage;
  workflow: WorkflowDefinition;
};

export function StageRunMain({
  activeRunId,
  events,
  onApproveBrief,
  onOpenConsole,
  onOpenRuntimePanel,
  onRegenerateBrief,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  onStageArtifactDraftChange,
  stageArtifactDraft,
  stageArtifactDraftError = '',
  stageArtifactDraftStatus = 'idle',
  runDefinition,
  stage,
  workflow,
}: Props) {
  const config = stageConfig(stage.type);
  const stageDisplayLabel = stage.label;
  const artifactState = stageArtifactState(stage, events);
  const sourceArtifactResult = artifactState.status === 'ready' ? artifactState.result : '';
  const artifactResult = currentStageArtifact(sourceArtifactResult, stageArtifactDraft);
  const chapterArtifact = stage.type === 'text' ? parseChapterArtifact(artifactResult).artifact : null;
  const characterResult = latestApprovedArtifact(events, 'cast');
  const characterBible = parseCharacterBibleArtifact(characterResult).artifact;
  const characters = characterBible?.subjects.map(({ id, kind, name }) => ({ id, kind, name })) ?? [];
  const scaleSuggestion = runDefinition
    ? suggestScalePlan(
      runDefinition.scale_profile,
      runDefinition.scale_profile.capacity_policy,
    )
    : null;
  const castDebutChapterLimit = scaleSuggestion?.chapterRange[0];
  const committedSpine = parseSpineArtifact(latestApprovedArtifact(events, 'spine')).artifact;
  const semanticContext = {
    characterBible,
    detailSceneRange: scaleSuggestion?.sceneRange,
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
    coverAssetRequired: runDefinition?.export_preferences.include_cover_image !== false,
  }) : null;
  const exportStatus = stage.type === 'export' ? artifactReadiness(parseExportArtifact(artifactResult)) : null;
  const providerUsage = latestProviderUsage(events);
  const pendingDecision = pendingStageDecision(
    events,
    stage.id,
    stage.type === 'text' && chapterArtifact?.chapter_id ? chapterArtifact.chapter_id : undefined,
  );
  const failureDecision = isFailureDecision(pendingDecision) ? pendingDecision : undefined;
  const recoverableFailureMessage = failureDecision
    ? failureMessageForDecision(events, failureDecision)
    : '';
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
            {onOpenConsole ? (
              <button className="stage-workbench-return" onClick={onOpenConsole} title="打开创作控制台" type="button">
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
      {showArtifact && failureDecision ? (
        <div className="vnext-contract-warning" role="alert">
          {recoverableFailureMessage || '本次生成未通过阶段合同，请重新生成。'}
        </div>
      ) : null}
      {artifactState.status === 'ready' && artifactState.source === 'fixture' ? <ArtifactFixtureNotice /> : null}
      {!showArtifact ? (
        <StageArtifactStatePanel
          label={stageDisplayLabel}
          onOpenConsole={onOpenConsole}
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
          totalChapters={castDebutChapterLimit}
        />
      ) : null}
      {showArtifact && stage.type === 'spine' ? <SpineStageView onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'volumes' ? <VolumeStageView characters={characters} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} spineTurns={committedSpine?.turns ?? []} /> : null}
      {showArtifact && stage.type === 'detail' ? <DetailStageViewVnext characters={characters} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} sceneRange={scaleSuggestion?.sceneRange} /> : null}
      {showArtifact && stage.type === 'text' ? <ChapterStageViewVnext onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} /> : null}
      {showArtifact && stage.type === 'cover' ? <CoverStageViewVnext coverAssetRequired={runDefinition?.export_preferences.include_cover_image !== false} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} runId={activeRunId} sourceResult={sourceArtifactResult} /> : null}
      {showArtifact && stage.type === 'export' ? <ExportStageViewVnext deliveryRevision={events.find((event) => event.stage_id === 'export' && event.type === 'artifact.committed')?.event_id ?? ''} onArtifactChange={(artifact) => onStageArtifactDraftChange(stage.id, sourceArtifactResult, JSON.stringify(artifact, null, 2))} readOnly={stageConfirmed} result={artifactResult} runId={activeRunId} /> : null}
      {showArtifact && (characterStatus ?? spineStatus ?? volumeStatus ?? detailStatus ?? coverStatus)?.missingLabels.length ? (
        <div className="vnext-contract-warning" role="alert">
          {(characterStatus ?? spineStatus ?? volumeStatus ?? detailStatus ?? coverStatus)?.missingLabels.join('、')}
        </div>
      ) : null}
      {!['brief', 'cast', 'spine', 'volumes', 'detail', 'text', 'cover', 'export'].includes(stage.type) ? (
        <section className="stage-run-card"><BookOpenText size={16} />暂未定义该阶段展示。</section>
      ) : null}
      </div>
      {(artifactState.status === 'ready' || failureDecision) && stage.type !== 'brief' ? (
        <StageDecisionControls
          completed={isCompleted}
          events={events}
          artifactMissingLabels={characterStatus?.missingLabels ?? spineStatus?.missingLabels ?? volumeStatus?.missingLabels ?? detailStatus?.missingLabels ?? writingStatus?.missingLabels ?? coverStatus?.missingLabels ?? exportStatus?.missingLabels ?? []}
          artifactReady={characterStatus?.ready ?? spineStatus?.ready ?? volumeStatus?.ready ?? detailStatus?.ready ?? writingStatus?.ready ?? coverStatus?.ready ?? exportStatus?.ready ?? true}
          onConfirmStageArtifact={(stageId) => onConfirmStageArtifact(stageId, artifactResult)}
          onRegenerateStageDraft={onRegenerateStageDraft}
          chapterId={chapterArtifact?.chapter_id ?? ''}
          stage={stage}
          stageArtifactDraftError={stageArtifactDraftError}
          stageArtifactDraftStatus={stageArtifactDraftStatus}
          workflow={workflow}
        />
      ) : null}
      {(artifactState.status === 'ready' || failureDecision) && stage.type === 'brief' ? (
        <StageDecisionControls
          completed={isCompleted}
          events={events}
          artifactReady
          onConfirmStageArtifact={() => onApproveBrief(artifactResult)}
          onRegenerateStageDraft={(_, direction) => { void onRegenerateBrief(direction); }}
          stage={stage}
          stageArtifactDraftError={stageArtifactDraftError}
          stageArtifactDraftStatus={stageArtifactDraftStatus}
          workflow={workflow}
        />
      ) : null}
    </>
  );
}
