import { describe, expect, it } from 'vitest';
import {
  exitWritingFocus,
  initialWritingViewState,
  selectWritingViewMode,
  writingChapterSwitchLocked,
} from './writingViewMode';

describe('writing view mode', () => {
  it('returns to the previous task view after focus mode', () => {
    const review = selectWritingViewMode(initialWritingViewState, 'review');
    const focus = selectWritingViewMode(review, 'focus');

    expect(focus).toEqual({ current: 'focus', restore: 'review' });
    expect(exitWritingFocus(focus)).toEqual({ current: 'review', restore: 'review' });
  });

  it('changes only view state and leaves an artifact reference untouched', () => {
    const artifact = { schema_version: 'chapter-artifact.v1', chapters: [{ id: 'chapter-1' }] };
    const next = selectWritingViewMode(initialWritingViewState, 'focus');

    expect(next.current).toBe('focus');
    expect(artifact.chapters[0].id).toBe('chapter-1');
  });

  it('locks chapter switching for every server-bound review operation', () => {
    expect(writingChapterSwitchLocked(true, null)).toBe(true);
    expect(writingChapterSwitchLocked(false, 'sync')).toBe(true);
    expect(writingChapterSwitchLocked(false, 'decision')).toBe(true);
    expect(writingChapterSwitchLocked(false, null)).toBe(false);
  });
});
