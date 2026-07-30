import { useEffect, useMemo, useState } from 'react';
import type { ChapterQualityRepairTarget, RunEvent, WorkflowDefinition } from '../contracts';
import { useChapterRevision } from '../state/useChapterRevision';
import { useChapterReview } from '../state/useChapterReview';
import { useCompactViewport } from '../state/useCompactViewport';
import { useStreamReveal } from '../state/useStreamReveal';
import { useWritingViewport } from '../state/useWritingViewport';
import { useWritingQualitySelection } from '../state/useWritingQualitySelection';
import { TensionCurve } from './TensionCurve';
import { buildTensionSeries } from './tensionTrackModel';
import { WritingChapterNav } from './WritingChapterNav';
import { WritingChapterWorkspace } from './WritingChapterWorkspace';
import { WritingContextBar } from './WritingContextBar';
import { ParallelDeliveryDialog } from './ParallelDeliveryDialog';
import { parallelDeliverySnapshot } from './parallelDeliveryModel';
import { WritingManuscriptEditor } from './WritingManuscriptEditor';
import { WritingReviewInspector } from './WritingReviewInspector';
import { WritingReviewRail } from './WritingReviewRail';
import { WritingStageDialogs } from './WritingStageDialogs';
import { WritingWorkbenchLayout, type WritingMobileSheetKey } from './WritingWorkbenchLayout';
import {
  updateWritingChapter,
  writingArtifact,
  writingReadiness,
  type WritingArtifact,
  type WritingChapter,
} from './writingArtifactModel';
import type { WritingViewportSnapshot } from './writingViewport';
import type { DetailChapterContext } from './writingContextPresentation';
import { writingChapterSwitchLocked, type WritingViewMode } from './writingViewMode';

type Props = {
  activeRunId: string;
  artifact: WritingArtifact;
  chapter: WritingChapter;
  detailChapter?: DetailChapterContext;
  dirty: boolean;
  events: RunEvent[];
  memoryEvents: RunEvent[];
  onArtifactChange: (artifact: WritingArtifact) => void;
  onExitFocus: () => void;
  onOpenRuntimePanel: (panel: 'character' | 'worldbuilding') => void;
  onQualityRepairHandled: () => void;
  onRepairQualityFinding: (target: ChapterQualityRepairTarget) => void;
  onSelectChapter: (chapterId: string) => void;
  onViewModeChange: (mode: WritingViewMode) => void;
  persistedChapter: WritingChapter;
  qualityRepairTarget: ChapterQualityRepairTarget | null;
  readOnly: boolean;
  streaming: boolean;
  trustedCharacterNames: string[];
  viewportSnapshots: { current: Map<string, WritingViewportSnapshot> };
  viewMode: WritingViewMode;
  workflow: WorkflowDefinition;
};

export function WritingWorkbenchContent({
  activeRunId,
  artifact,
  chapter,
  detailChapter,
  dirty,
  events,
  memoryEvents,
  onArtifactChange,
  onExitFocus,
  onOpenRuntimePanel,
  onQualityRepairHandled,
  onRepairQualityFinding,
  onSelectChapter,
  onViewModeChange,
  persistedChapter,
  qualityRepairTarget,
  readOnly,
  streaming,
  trustedCharacterNames,
  viewportSnapshots,
  viewMode,
  workflow,
}: Props) {
  const readiness = useMemo(() => writingReadiness(artifact), [artifact]);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [mobileSheet, setMobileSheet] = useState<WritingMobileSheetKey>(null);
  const [deliveryOpen, setDeliveryOpen] = useState(false);
  const compact = useCompactViewport();
  const { pace: streamPace, text: visibleText } = useStreamReveal(chapter.content, { active: streaming, mode: 'word', tickMs: 44 });
  const viewport = useWritingViewport({
    chapterId: chapter.id,
    layoutKey: `${compact ? 'compact' : 'desktop'}:${viewMode}`,
    snapshots: viewportSnapshots,
    streaming,
    visibleText,
  });
  const revision = useChapterRevision({
    activeRunId,
    chapter,
    nodeId: 'text',
    persistedChapter,
    workflowId: workflow.id,
    onArtifactApplied: (value) => onArtifactChange(writingArtifact(JSON.stringify(value), events)),
  });
  const review = useChapterReview({
    activeRunId,
    chapter,
    nodeId: 'text',
    persistedChapter,
    workflowId: workflow.id,
    onArtifactApplied: (value) => onArtifactChange(writingArtifact(JSON.stringify(value), events)),
  });
  const { readerRef, rememberCursor } = viewport;
  const qualitySelection = useWritingQualitySelection({
    chapter,
    onClearRevisionError: revision.clearError,
    onQualityRepairHandled,
    qualityRepairTarget,
    readerRef,
    readOnly,
    rememberCursor,
    streaming,
  });
  const { captureSelection, repairError, selection, setRepairError, setSelection } = qualitySelection;
  const chapterSwitchLocked = writingChapterSwitchLocked(revision.busy, review.busy);
  const delivery = useMemo(() => parallelDeliverySnapshot(events, artifact), [artifact, events]);
  const tensionAvailable = useMemo(
    () => !buildTensionSeries(artifact.chapters, events, chapter.id).empty,
    [artifact.chapters, chapter.id, events],
  );

  useEffect(() => {
    if (!compact) setMobileSheet(null);
  }, [compact]);

  const editorLocked = readOnly || streaming;
  const updateChapter = (patch: Parameters<typeof updateWritingChapter>[2]) => {
    onArtifactChange(updateWritingChapter(artifact, chapter.id, patch));
  };
  const selectChapter = (chapterId: string) => {
    if (chapterSwitchLocked || chapterId === chapter.id) return;
    onQualityRepairHandled();
    setMobileSheet(null);
    onSelectChapter(chapterId);
  };
  const openVersions = () => {
    revision.clearError();
    setVersionsOpen(true);
  };
  const reviewLabel = review.busy === 'sync'
    ? '正在同步复检'
    : review.busy === 'decision'
      ? '正在提交决策'
      : chapter.summary_dirty
        ? '摘要待同步'
        : chapter.writeback_proposal?.status === 'pending'
          ? '写回待决策'
          : '查看质量与写回';

  return (
    <>
      <WritingWorkbenchLayout
        busy={chapterSwitchLocked}
        chapterLabel={chapter.generated_title || chapter.title}
        chapterRail={(
          <WritingChapterNav
            activeChapterId={chapter.id}
            chapters={artifact.chapters}
            compact
            locked={chapterSwitchLocked}
            onSelect={selectChapter}
          />
        )}
        chapterWorkspace={(
          <WritingChapterWorkspace
            activeChapterId={chapter.id}
            chapters={artifact.chapters}
            detailChapter={detailChapter}
            locked={chapterSwitchLocked}
            onOpenVersions={openVersions}
            onSelectChapter={selectChapter}
            onSummaryChange={(summary) => updateChapter({ summary })}
            readOnly={readOnly || streaming}
            revisionHistory={chapter.revision_history}
            selectedChapter={chapter}
            trustedCharacterNames={trustedCharacterNames}
            versionCount={chapter.version_history.length}
          />
        )}
        compact={compact}
        contextBar={<WritingContextBar artifact={artifact} chapter={chapter} delivery={delivery} detailChapter={detailChapter} onOpenDelivery={() => setDeliveryOpen(true)} readOnly={readOnly} readiness={readiness} streaming={streaming} />}
        editor={(
        <WritingManuscriptEditor
          chapter={chapter}
          dirty={dirty}
          editorLocked={editorLocked}
          followingStream={viewport.following}
          onCancelRepair={() => {
            setSelection(null);
            onQualityRepairHandled();
          }}
          onCaptureSelection={captureSelection}
          onChange={(target) => {
            rememberCursor(target);
            setSelection(null);
            setRepairError('');
            onQualityRepairHandled();
            updateChapter({ content: target.value });
          }}
          onClearRevisionError={revision.clearError}
          onGenerateRevision={(operation, direction) => {
            if (selection) void revision.generate(selection, operation, direction);
          }}
          onResumeStream={viewport.resumeFollowing}
          onScroll={viewport.onScroll}
          qualityRepairTarget={qualityRepairTarget?.chapter_id === chapter.id ? qualityRepairTarget : null}
          readOnly={readOnly}
          readerRef={readerRef}
          readiness={readiness}
          repairError={repairError}
          revisionBusy={revision.busy}
          revisionError={revision.candidate ? '' : revision.error}
          selection={selection}
          streaming={streaming}
          streamPace={streamPace}
          visibleText={visibleText}
          workflow={workflow}
        />
        )}
        mobileSheet={mobileSheet}
        onExitFocus={onExitFocus}
        onMobileSheetChange={setMobileSheet}
        onViewModeChange={onViewModeChange}
        reviewInspector={(
        <WritingReviewInspector
          busy={review.busy}
          chapter={chapter}
          error={review.error}
          events={[...events, ...memoryEvents]}
          onClearError={review.clearError}
          onDecide={(proposal, decision, conflicts) => void review.decide(proposal, decision, conflicts)}
          onOpenCharacter={() => {
            setMobileSheet(null);
            onOpenRuntimePanel('character');
          }}
          onOpenWorldbuilding={() => {
            setMobileSheet(null);
            onOpenRuntimePanel('worldbuilding');
          }}
          onRepair={(target) => {
            setMobileSheet(null);
            onRepairQualityFinding(target);
          }}
          onSync={() => void review.sync()}
          panelIdPrefix={compact ? 'writing-review-mobile' : 'writing-review-desktop'}
          qualityMode={workflow.quality_mode}
          readOnly={readOnly || streaming}
        />
        )}
        reviewLabel={reviewLabel}
        reviewRail={<WritingReviewRail chapter={chapter} onExpand={() => onViewModeChange('review')} />}
        tensionStrip={tensionAvailable ? (
          <div className="writing-signature-band">
            <TensionCurve
              activeChapterId={chapter.id}
              chapters={artifact.chapters}
              events={events}
              locked={chapterSwitchLocked}
              onSelectChapter={selectChapter}
            />
          </div>
        ) : undefined}
        viewMode={viewMode}
      />
      <WritingStageDialogs
        revision={revision.candidate ? {
          busy: revision.busy,
          candidate: revision.candidate,
          error: revision.error,
          onAccept: () => void revision.apply().then((applied) => {
            if (applied) {
              setSelection(null);
              onQualityRepairHandled();
            }
          }),
          onClose: revision.clearCandidate,
        } : null}
        versionHistory={versionsOpen ? {
          busy: revision.busy,
          currentVersion: chapter.version,
          error: revision.error,
          onClose: () => setVersionsOpen(false),
          onRestore: (versionId) => void revision.restore(versionId).then((restored) => {
            if (restored) setVersionsOpen(false);
          }),
          versions: chapter.version_history,
        } : null}
      />
      {deliveryOpen ? <ParallelDeliveryDialog activeRunId={activeRunId} artifact={artifact} onClose={() => setDeliveryOpen(false)} snapshot={delivery} /> : null}
    </>
  );
}
