import { useEffect, useRef, useState } from 'react';
import type {
  ChapterRevisionCandidate,
  ChapterRevisionOperation,
  ChapterSelection,
} from '../contracts';
import type { WritingChapter } from '../running/writingArtifactModel';
import {
  chapterRevisionRequestId,
  chapterRevisionSignature,
} from '../running/chapterSelectionModel';
import {
  applyChapterSelectionRevision,
  generateChapterSelectionRevision,
  restoreChapterVersion,
} from '../services/runApi';

type Options = {
  activeRunId: string;
  chapter: WritingChapter;
  nodeId: string;
  persistedChapter: WritingChapter;
  workflowId: string;
  onArtifactApplied: (artifact: unknown) => void;
};

export function useChapterRevision({
  activeRunId,
  chapter,
  nodeId,
  persistedChapter,
  workflowId,
  onArtifactApplied,
}: Options) {
  const [busy, setBusy] = useState(false);
  const [candidate, setCandidate] = useState<ChapterRevisionCandidate | null>(null);
  const [error, setError] = useState('');
  const persistedRef = useRef(persistedChapter);

  useEffect(() => {
    persistedRef.current = persistedChapter;
    setCandidate(null);
    setError('');
  }, [
    persistedChapter.content,
    persistedChapter.id,
    persistedChapter.summary,
    persistedChapter.summary_dirty,
    persistedChapter.version,
  ]);

  async function generate(
    selection: ChapterSelection,
    operation: ChapterRevisionOperation,
    direction: string,
  ) {
    if (!activeRunId || busy) return false;
    setBusy(true);
    setError('');
    try {
      const [baseSignature, persistedSignature] = await Promise.all([
        chapterRevisionSignature(chapter),
        chapterRevisionSignature(persistedRef.current),
      ]);
      const response = await generateChapterSelectionRevision(activeRunId, {
        workflow_id: workflowId,
        node_id: nodeId,
        chapter_id: chapter.id,
        start: selection.start,
        end: selection.end,
        selected_text: selection.text,
        operation,
        direction: direction.trim(),
        base_version: chapter.version,
        base_signature: baseSignature,
        persisted_signature: persistedSignature,
        base_chapter: chapter as unknown as Record<string, unknown>,
        request_id: chapterRevisionRequestId('revision'),
      });
      setCandidate(response.candidate);
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!candidate || busy) return false;
    setBusy(true);
    setError('');
    try {
      const response = await applyChapterSelectionRevision(activeRunId, {
        workflow_id: workflowId,
        node_id: nodeId,
        request_id: candidate.request_id,
        candidate_signature: candidate.candidate_signature,
      });
      persistedRef.current = response.chapter as unknown as WritingChapter;
      onArtifactApplied(response.artifact);
      setCandidate(null);
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function restore(versionId: string) {
    if (!activeRunId || busy) return false;
    setBusy(true);
    setError('');
    try {
      const [baseSignature, persistedSignature] = await Promise.all([
        chapterRevisionSignature(chapter),
        chapterRevisionSignature(persistedRef.current),
      ]);
      const response = await restoreChapterVersion(activeRunId, {
        workflow_id: workflowId,
        node_id: nodeId,
        chapter_id: chapter.id,
        version_id: versionId,
        base_version: chapter.version,
        base_signature: baseSignature,
        persisted_signature: persistedSignature,
        base_chapter: chapter as unknown as Record<string, unknown>,
        request_id: chapterRevisionRequestId('restore'),
      });
      persistedRef.current = response.chapter as unknown as WritingChapter;
      onArtifactApplied(response.artifact);
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(false);
    }
  }

  return {
    apply,
    busy,
    candidate,
    clearCandidate: () => {
      if (!busy) setCandidate(null);
    },
    clearError: () => setError(''),
    error,
    generate,
    restore,
  };
}


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '章节修订失败，请稍后重试。';
}
