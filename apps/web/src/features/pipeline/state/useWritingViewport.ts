import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  clampWritingViewport,
  isSelectableReader,
  isWritingViewportAtTail,
  readerContentLength,
  type ManuscriptReaderElement,
  type WritingViewportSnapshot,
} from '../running/writingViewport';

type ViewportStore = {
  current: Map<string, WritingViewportSnapshot>;
};

type Options = {
  chapterId: string;
  layoutKey: string;
  snapshots: ViewportStore;
  streaming: boolean;
  visibleText: string;
};

export function useWritingViewport({ chapterId, layoutKey, snapshots, streaming, visibleText }: Options) {
  const initial = clampWritingViewport(snapshots.current.get(chapterId), visibleText.length);
  const [following, setFollowing] = useState(initial.following);
  const readerRef = useRef<ManuscriptReaderElement | null>(null);

  const remember = useCallback((target: ManuscriptReaderElement, nextFollowing = following) => {
    const previous = snapshots.current.get(chapterId);
    snapshots.current.set(chapterId, {
      following: nextFollowing,
      scrollTop: target.scrollTop,
      selectionStart: isSelectableReader(target) ? target.selectionStart : previous?.selectionStart ?? 0,
      selectionEnd: isSelectableReader(target) ? target.selectionEnd : previous?.selectionEnd ?? 0,
    });
  }, [chapterId, following, snapshots]);

  useLayoutEffect(() => {
    const reader = readerRef.current;
    if (!reader) return;
    const saved = clampWritingViewport(snapshots.current.get(chapterId), readerContentLength(reader));
    setFollowing(saved.following);
    if (isSelectableReader(reader)) reader.setSelectionRange(saved.selectionStart, saved.selectionEnd);
    reader.scrollTop = streaming && saved.following ? reader.scrollHeight : saved.scrollTop;
  }, [chapterId, layoutKey, snapshots, streaming]);

  useEffect(() => {
    const reader = readerRef.current;
    if (!reader || !streaming || !following) return;
    reader.scrollTop = reader.scrollHeight;
    remember(reader, true);
  }, [following, remember, streaming, visibleText]);

  useEffect(() => {
    const reader = readerRef.current;
    if (!reader || !streaming || !following || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      reader.scrollTop = reader.scrollHeight;
      remember(reader, true);
    });
    observer.observe(reader);
    return () => observer.disconnect();
  }, [following, remember, streaming]);

  const onScroll = (target: ManuscriptReaderElement) => {
    const nextFollowing = streaming
      ? isWritingViewportAtTail(target.scrollHeight, target.scrollTop, target.clientHeight)
      : following;
    if (nextFollowing !== following) setFollowing(nextFollowing);
    remember(target, nextFollowing);
  };

  const resumeFollowing = () => {
    const reader = readerRef.current;
    if (!reader) return;
    setFollowing(true);
    reader.scrollTop = reader.scrollHeight;
    remember(reader, true);
  };

  return {
    following,
    onScroll,
    readerRef,
    rememberCursor: remember,
    resumeFollowing,
  };
}
