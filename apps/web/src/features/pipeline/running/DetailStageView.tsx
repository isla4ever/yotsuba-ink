import { AnimatePresence } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { ChapterBlueprintDialog } from './ChapterBlueprintDialog';
import { DetailChapterLedger } from './DetailChapterLedger';
import { DetailCharacterShiftDialog } from './DetailCharacterShiftDialog';
import { DetailConstructionTable } from './DetailConstructionTable';
import { DetailContextBar } from './DetailContextBar';
import { DetailCoverageHeatStrip } from './DetailCoverageHeatStrip';
import type { DetailBaseline, DetailReadiness } from './detailArtifactModel';
import { DetailForeshadowDialog } from './DetailForeshadowDialog';
import { DetailWorldWikiDialog } from './DetailWorldWikiDialog';
import { detailArtifact, type DetailOutlineArtifact } from './stageArtifacts';
import { activeIndexFor, deltasBySection } from './stageViewData';
import { StageToast } from './StageToast';

type Props = {
  baseline: DetailBaseline;
  deltas?: Array<{ section: string; delta: string }>;
  generating?: boolean;
  onArtifactChange: (artifact: DetailOutlineArtifact) => void;
  readiness: DetailReadiness;
  readOnly?: boolean;
  result: string;
  sourceResult?: string;
};

type DetailChapter = DetailOutlineArtifact['chapters'][number];
type DetailWritebackEditor = 'wiki' | 'character' | 'foreshadow';

export function DetailStageView({ baseline, deltas = [], generating, onArtifactChange, readiness, readOnly = false, result, sourceResult = result }: Props) {
  const [artifact, setArtifact] = useState(() => detailArtifact(result));
  const [selectedChapterIndex, setSelectedChapterIndex] = useState<number | null>(null);
  const [editingChapterIndex, setEditingChapterIndex] = useState<number | null>(null);
  const [writebackEditor, setWritebackEditor] = useState<DetailWritebackEditor | null>(null);
  const [toast, setToast] = useState('');
  useEffect(() => setArtifact(detailArtifact(result)), [result]);
  useEffect(() => {
    setEditingChapterIndex(null);
    setSelectedChapterIndex(null);
    setWritebackEditor(null);
  }, [sourceResult]);
  const deltaBySection = useMemo(() => deltasBySection(deltas), [deltas]);
  const liveIndex = generating ? activeIndexFor(artifact.chapters.map((chapter) => chapter.chapter), deltaBySection) : artifact.chapters.length - 1;
  const visibleChapters = generating ? artifact.chapters.slice(0, Math.max(1, liveIndex + 1)) : artifact.chapters;
  const activeChapterIndex = Math.max(0, Math.min(selectedChapterIndex ?? liveIndex, visibleChapters.length - 1));
  const legacyFinalized = readOnly && !generating && !readiness.ready;
  const selectedChapter = visibleChapters[activeChapterIndex] ?? artifact.chapters[0] ?? null;
  const editingTarget = editingChapterIndex === null || !artifact.chapters[editingChapterIndex]
    ? null
    : { chapter: artifact.chapters[editingChapterIndex], index: editingChapterIndex };
  const commit = (update: (current: DetailOutlineArtifact) => DetailOutlineArtifact) => {
    if (readOnly) return;
    setArtifact((current) => {
      const next = update(current);
      onArtifactChange(next);
      return next;
    });
  };
  const updateChapter = (index: number, patch: Partial<DetailChapter>) => {
    commit((current) => ({
      ...current,
      chapters: current.chapters.map((chapter, chapterIndex) => chapterIndex === index ? { ...chapter, ...patch } : chapter),
    }));
  };
  const openWritebackEditor = (editor: DetailWritebackEditor) => {
    if (!selectedChapter) return;
    setSelectedChapterIndex(activeChapterIndex);
    setWritebackEditor(editor);
  };
  const saveWriteback = (chapterIndex: number, patch: Partial<Pick<DetailChapter, 'character_shift' | 'fact_reveals' | 'wiki_candidates' | 'foreshadow'>>, message: string) => {
    updateChapter(chapterIndex, patch);
    setSelectedChapterIndex(chapterIndex);
    setWritebackEditor(null);
    setToast(message);
  };

  return (
    <div className="detail-outline-board detail-workbench-v2 detail-workbench-phase84">
      <StageToast message={toast} onDismiss={() => setToast('')} />
      <DetailContextBar artifact={artifact} generating={Boolean(generating)} legacyFinalized={legacyFinalized} readiness={readiness} selectedChapter={selectedChapter} />
      <DetailCoverageHeatStrip
        baseline={baseline}
        chapters={visibleChapters}
        legacyFinalized={legacyFinalized}
        onSelectChapter={setSelectedChapterIndex}
        selectedChapterIndex={activeChapterIndex}
      />
      <DetailConstructionTable
        baseline={baseline}
        chapters={visibleChapters}
        deltaBySection={deltaBySection}
        generating={Boolean(generating)}
        liveIndex={liveIndex}
        onOpenChapter={(index) => {
          setSelectedChapterIndex(index);
          setEditingChapterIndex(index);
        }}
        selectedChapterIndex={activeChapterIndex}
      />
      <DetailChapterLedger
        chapter={selectedChapter}
        onEditBlueprint={() => {
          if (selectedChapter) setEditingChapterIndex(activeChapterIndex);
        }}
        onOpenWriteback={openWritebackEditor}
        readOnly={readOnly}
      />
      <AnimatePresence>
        {editingTarget ? (
          <ChapterBlueprintDialog
            baseline={baseline}
            chapter={editingTarget.chapter}
            chapterIndex={editingTarget.index}
            chapters={artifact.chapters}
            onChapterChange={(index) => {
              setSelectedChapterIndex(index);
              setEditingChapterIndex(index);
            }}
            onClose={() => setEditingChapterIndex(null)}
            onSave={(values) => {
              updateChapter(editingTarget.index, values);
              setSelectedChapterIndex(editingTarget.index);
              setEditingChapterIndex(null);
              setToast('章节蓝图已保存到当前稿');
            }}
            readOnly={readOnly}
          />
        ) : null}
        {writebackEditor === 'wiki' && selectedChapter ? (
          <DetailWorldWikiDialog
            baseline={baseline}
            chapter={selectedChapter}
            chapterIndex={activeChapterIndex}
            chapters={artifact.chapters}
            key={`wiki-${activeChapterIndex}`}
            onChapterChange={setSelectedChapterIndex}
            onClose={() => setWritebackEditor(null)}
            onSave={(chapterIndex, values) => saveWriteback(chapterIndex, values, '事实与 Wiki 已保存到当前稿')}
            readOnly={readOnly}
          />
        ) : null}
        {writebackEditor === 'character' && selectedChapter ? (
          <DetailCharacterShiftDialog
            baseline={baseline}
            chapter={selectedChapter}
            chapterIndex={activeChapterIndex}
            chapters={artifact.chapters}
            key={`character-${activeChapterIndex}`}
            onChapterChange={setSelectedChapterIndex}
            onClose={() => setWritebackEditor(null)}
            onSave={(chapterIndex, character_shift) => saveWriteback(chapterIndex, { character_shift }, '人物变化已保存到当前稿')}
            readOnly={readOnly}
          />
        ) : null}
        {writebackEditor === 'foreshadow' && selectedChapter ? (
          <DetailForeshadowDialog
            baseline={baseline}
            chapter={selectedChapter}
            chapterIndex={activeChapterIndex}
            chapters={artifact.chapters}
            key={`foreshadow-${activeChapterIndex}`}
            onChapterChange={setSelectedChapterIndex}
            onClose={() => setWritebackEditor(null)}
            onSave={(chapterIndex, foreshadow) => saveWriteback(chapterIndex, { foreshadow }, '伏笔账本已保存到当前稿')}
            readOnly={readOnly}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}
