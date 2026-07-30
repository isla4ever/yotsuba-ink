import { describe, expect, it } from 'vitest';
import {
  STREAM_REVEAL_BACKLOG_LIMIT,
  STREAM_REVEAL_BOOST_BACKLOG,
  nextRevealLength,
  shouldCompleteStreamReveal,
  streamRevealPace,
} from './streamText';

describe('stream reveal motion policy', () => {
  it('completes immediately when reduced motion is requested', () => {
    expect(shouldCompleteStreamReveal({
      active: true,
      backlog: 24,
      documentHidden: false,
      reducedMotion: true,
    })).toBe(true);
  });

  it('completes immediately when content backlog reaches the safety limit', () => {
    expect(shouldCompleteStreamReveal({
      active: true,
      backlog: STREAM_REVEAL_BACKLOG_LIMIT,
      documentHidden: false,
      reducedMotion: false,
    })).toBe(true);
  });

  it('completes immediately while the document is hidden', () => {
    expect(shouldCompleteStreamReveal({
      active: true,
      backlog: 12,
      documentHidden: true,
      reducedMotion: false,
    })).toBe(true);
  });

  it('stops advancing after the complete target is visible', () => {
    expect(nextRevealLength('完整内容', '完整内容', 'smooth')).toBe('完整内容'.length);
  });

  it('advances word mode by small word-sized steps when backlog is calm', () => {
    const target = '雾港的旧声，在电台里复活。剩下的句子继续延伸。';
    const next = nextRevealLength('', target, 'word');
    expect(next).toBeGreaterThan(0);
    expect(next).toBeLessThanOrEqual(27);
  });

  it('switches the pace gear exactly when backlog crosses the boost threshold', () => {
    expect(streamRevealPace(0)).toBe('steady');
    expect(streamRevealPace(STREAM_REVEAL_BOOST_BACKLOG)).toBe('steady');
    expect(streamRevealPace(STREAM_REVEAL_BOOST_BACKLOG + 1)).toBe('boost');
  });
});
