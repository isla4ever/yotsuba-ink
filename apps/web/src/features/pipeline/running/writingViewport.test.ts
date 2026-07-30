import { describe, expect, it } from 'vitest';
import { clampWritingViewport, isWritingViewportAtTail } from './writingViewport';

describe('writingViewport', () => {
  it('only follows streaming content while the reader remains near the tail', () => {
    expect(isWritingViewportAtTail(1000, 560, 420)).toBe(true);
    expect(isWritingViewportAtTail(1000, 420, 420)).toBe(false);
  });

  it('keeps stored scroll state while clamping stale cursor offsets', () => {
    expect(clampWritingViewport({
      following: false,
      scrollTop: 188,
      selectionStart: 90,
      selectionEnd: 120,
    }, 100)).toEqual({
      following: false,
      scrollTop: 188,
      selectionStart: 90,
      selectionEnd: 100,
    });
  });
});
