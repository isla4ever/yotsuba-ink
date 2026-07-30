import { BookOpenText } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChapterQualityRepairTarget, RunEvent, WorkflowDefinition } from '../contracts';
import { currentChapter } from './stageRunUtils';
import { writingArtifact, type WritingArtifact } from './writingArtifactModel';
import type { WritingViewportSnapshot } from './writingViewport';
import {
  exitWritingFocus,
  initialWritingViewState,
  selectWritingViewMode,
} from './writingViewMode';
import { WritingWorkbenchContent } from './WritingWorkbenchContent';
import { latestApprovedArtifact, latestResult } from './stageRunUtils';
import { summaryInfoBaseline } from './summaryArtifactModel';
import { detailArtifact } from './stageArtifacts';

type Props = {
  activeRunId: string;
  dirty?: boolean;
  events: RunEvent[];
  memoryEvents: RunEvent[];
  onArtifactChange: (artifact: WritingArtifact) => void;
  onOpenRuntimePanel: (panel: 'character' | 'worldbuilding') => void;
  onQualityRepairHandled: () => void;
  onRepairQualityFinding: (target: ChapterQualityRepairTarget) => void;
  onSelectedChapterChange: (chapterId: string) => void;
  qualityRepairTarget: ChapterQualityRepairTarget | null;
  readOnly?: boolean;
  result: string;
  sourceResult: string;
  stageId: string;
  workflow: WorkflowDefinition;
};

export function WritingStageView({
  activeRunId,
  dirty = false,
  events,
  memoryEvents,
  onArtifactChange,
  onOpenRuntimePanel,
  onQualityRepairHandled,
  onRepairQualityFinding,
  onSelectedChapterChange,
  qualityRepairTarget,
  readOnly = false,
  result,
  sourceResult,
  stageId,
  workflow,
}: Props) {
  const artifact = useMemo(() => writingArtifact(result, events), [events, result]);
  const persisted = useMemo(() => writingArtifact(sourceResult, events), [events, sourceResult]);
  const infoStageId = workflow.nodes.find((stage) => stage.type === 'info_recommend')?.id ?? 'info';
  const trustedCharacterNames = summaryInfoBaseline(
    latestApprovedArtifact(events, infoStageId) || latestResult(events, infoStageId),
  ).characters.map((character) => character.name);
  const detailStageId = workflow.nodes.find((stage) => stage.type === 'detail_outline')?.id ?? 'detail';
  const detailChapters = detailArtifact(
    latestApprovedArtifact(events, detailStageId) || latestResult(events, detailStageId),
  ).chapters;
  const liveChapter = currentChapter(events);
  const generating = !events.some((event) => event.type === 'node_completed' && event.node_id === stageId);
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [viewState, setViewState] = useState(initialWritingViewState);
  const viewportSnapshots = useRef(new Map<string, WritingViewportSnapshot>());
  const liveArtifactChapter = artifact.chapters.find((chapter) => chapter.title === liveChapter);

  useEffect(() => {
    if (generating && liveArtifactChapter?.id) setSelectedChapterId(liveArtifactChapter.id);
    else if (!selectedChapterId && artifact.chapters[0]?.id) setSelectedChapterId(artifact.chapters[0].id);
  }, [artifact.chapters, generating, liveArtifactChapter?.id, selectedChapterId]);
  useEffect(() => {
    if (qualityRepairTarget?.chapter_id && artifact.chapters.some((chapter) => chapter.id === qualityRepairTarget.chapter_id)) {
      setSelectedChapterId(qualityRepairTarget.chapter_id);
    }
  }, [artifact.chapters, qualityRepairTarget?.chapter_id]);
  useEffect(() => {
    if (viewState.current !== 'focus') return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setViewState(exitWritingFocus);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [viewState.current]);

  const activeChapter = artifact.chapters.find((chapter) => chapter.id === selectedChapterId) ?? artifact.chapters[0];
  useEffect(() => {
    if (activeChapter?.id) onSelectedChapterChange(activeChapter.id);
  }, [activeChapter?.id, onSelectedChapterChange]);
  if (!activeChapter) {
    return <section className="writing-stage-empty"><BookOpenText size={18} /><p>等待章节上下文和正文稿件写入。</p></section>;
  }
  const persistedChapter = persisted.chapters.find((chapter) => chapter.id === activeChapter.id) ?? activeChapter;
  const activeChapterIndex = Math.max(0, artifact.chapters.findIndex((chapter) => chapter.id === activeChapter.id));
  return (
    <WritingWorkbenchContent
      activeRunId={activeRunId}
      artifact={artifact}
      chapter={activeChapter}
      detailChapter={detailChapters[activeChapterIndex]}
      dirty={dirty}
      events={events}
      memoryEvents={memoryEvents}
      key={activeChapter.id}
      onArtifactChange={onArtifactChange}
      onExitFocus={() => setViewState(exitWritingFocus)}
      onOpenRuntimePanel={onOpenRuntimePanel}
      onQualityRepairHandled={onQualityRepairHandled}
      onRepairQualityFinding={onRepairQualityFinding}
      onSelectChapter={setSelectedChapterId}
      onViewModeChange={(mode) => setViewState((current) => selectWritingViewMode(current, mode))}
      persistedChapter={persistedChapter}
      qualityRepairTarget={qualityRepairTarget}
      readOnly={readOnly}
      streaming={Boolean(generating && activeChapter.title === liveChapter && activeChapter.status !== 'completed')}
      trustedCharacterNames={trustedCharacterNames}
      viewportSnapshots={viewportSnapshots}
      viewMode={viewState.current}
      workflow={workflow}
    />
  );
}
