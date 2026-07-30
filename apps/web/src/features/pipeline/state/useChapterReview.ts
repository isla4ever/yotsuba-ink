import { useEffect, useRef, useState } from 'react';
import type { ChapterWritebackProposal } from '../contracts';
import type { WritingChapter } from '../running/writingArtifactModel';
import { chapterRevisionRequestId, chapterRevisionSignature } from '../running/chapterSelectionModel';
import { decideChapterWritebackProposal, syncChapterSummary } from '../services/runApi';

type Options = {
  activeRunId: string;
  chapter: WritingChapter;
  nodeId: string;
  persistedChapter: WritingChapter;
  workflowId: string;
  onArtifactApplied: (artifact: unknown) => void;
};

export function useChapterReview({
  activeRunId,
  chapter,
  nodeId,
  persistedChapter,
  workflowId,
  onArtifactApplied,
}: Options) {
  const [busy, setBusy] = useState<'sync' | 'decision' | null>(null);
  const [error, setError] = useState('');
  const persistedRef = useRef(persistedChapter);

  useEffect(() => {
    persistedRef.current = persistedChapter;
    setError('');
  }, [
    persistedChapter.content,
    persistedChapter.id,
    persistedChapter.summary,
    persistedChapter.summary_dirty,
    persistedChapter.version,
  ]);

  async function sync() {
    if (!activeRunId || busy || !chapter.summary.trim()) return false;
    setBusy('sync');
    setError('');
    try {
      const [baseSignature, persistedSignature] = await Promise.all([
        chapterRevisionSignature(chapter),
        chapterRevisionSignature(persistedRef.current),
      ]);
      const response = await syncChapterSummary(activeRunId, chapter.id, {
        workflow_id: workflowId,
        node_id: nodeId,
        chapter_id: chapter.id,
        summary: chapter.summary.trim(),
        base_version: chapter.version,
        base_signature: baseSignature,
        persisted_signature: persistedSignature,
        base_chapter: chapter as unknown as Record<string, unknown>,
        request_id: chapterRevisionRequestId('summary-sync'),
      });
      persistedRef.current = response.chapter as unknown as WritingChapter;
      onArtifactApplied(response.artifact);
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function decide(
    proposal: ChapterWritebackProposal,
    decision: 'accepted' | 'rejected',
    conflictResolutions: NonNullable<ChapterWritebackProposal['conflict_resolutions']> = {},
  ) {
    if (!activeRunId || busy) return false;
    setBusy('decision');
    setError('');
    try {
      const baseSignature = await chapterRevisionSignature(chapter);
      const response = await decideChapterWritebackProposal(activeRunId, chapter.id, {
        workflow_id: workflowId,
        node_id: nodeId,
        chapter_id: chapter.id,
        proposal_id: proposal.id,
        proposal_signature: proposal.proposal_signature,
        decision,
        base_version: chapter.version,
        base_signature: baseSignature,
        request_id: chapterRevisionRequestId(`proposal-${decision}`),
        conflict_resolutions: conflictResolutions,
      });
      persistedRef.current = response.chapter as unknown as WritingChapter;
      onArtifactApplied(response.artifact);
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(null);
    }
  }

  return {
    busy,
    clearError: () => setError(''),
    decide,
    error,
    sync,
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '章节复检失败，请稍后重试。';
}
