import { useEffect, useState, type MutableRefObject } from 'react';
import type { ChapterQualityRepairTarget, ChapterSelection } from '../contracts';
import { chapterRepairSelection, chapterSelection } from '../running/chapterSelectionModel';
import type { WritingChapter } from '../running/writingArtifactModel';
import { isSelectableReader, type ManuscriptReaderElement } from '../running/writingViewport';

type Options = {
  chapter: WritingChapter;
  onClearRevisionError: () => void;
  onQualityRepairHandled: () => void;
  qualityRepairTarget: ChapterQualityRepairTarget | null;
  readerRef: MutableRefObject<ManuscriptReaderElement | null>;
  readOnly: boolean;
  rememberCursor: (target: ManuscriptReaderElement, nextFollowing?: boolean) => void;
  streaming: boolean;
};

export function useWritingQualitySelection({
  chapter,
  onClearRevisionError,
  onQualityRepairHandled,
  qualityRepairTarget,
  readerRef,
  readOnly,
  rememberCursor,
  streaming,
}: Options) {
  const [selection, setSelection] = useState<ChapterSelection | null>(null);
  const [repairError, setRepairError] = useState('');

  useEffect(() => {
    if (!qualityRepairTarget || qualityRepairTarget.chapter_id !== chapter.id || readOnly || streaming) return;
    let cancelled = false;
    let frame = 0;
    void chapterRepairSelection(chapter, qualityRepairTarget).then((nextSelection) => {
      if (cancelled) return;
      if (!nextSelection) {
        setRepairError('质量定位已过期，请同步摘要并重新复检后再定位。');
        onQualityRepairHandled();
        return;
      }
      setRepairError('');
      setSelection(nextSelection);
      frame = requestAnimationFrame(() => {
        const reader = readerRef.current;
        if (!reader || !isSelectableReader(reader)) return;
        reader.focus();
        reader.setSelectionRange(nextSelection.start, nextSelection.end);
        const ratio = nextSelection.start / Math.max(1, reader.value.length);
        reader.scrollTop = Math.max(0, reader.scrollHeight * ratio - reader.clientHeight * 0.35);
        rememberCursor(reader);
      });
    });
    return () => {
      cancelled = true;
      if (frame) cancelAnimationFrame(frame);
    };
  }, [chapter, onQualityRepairHandled, qualityRepairTarget, readOnly, readerRef, rememberCursor, streaming]);

  const captureSelection = (target: HTMLTextAreaElement) => {
    rememberCursor(target);
    if (readOnly || streaming) return;
    const nextSelection = chapterSelection(target.value, target.selectionStart, target.selectionEnd);
    if (qualityRepairTarget && (
      nextSelection?.start !== qualityRepairTarget.start
      || nextSelection?.end !== qualityRepairTarget.end
      || nextSelection?.text !== qualityRepairTarget.selected_text
    )) onQualityRepairHandled();
    setSelection(nextSelection);
    setRepairError('');
    onClearRevisionError();
  };

  return { captureSelection, repairError, selection, setRepairError, setSelection };
}
