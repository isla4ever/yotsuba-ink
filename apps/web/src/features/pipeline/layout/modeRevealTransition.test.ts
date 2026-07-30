import { describe, expect, it, vi } from 'vitest';
import {
  MODE_REVEAL_DURATION_MS,
  maxRevealRadius,
  runModeRevealTransition,
  supportsViewTransitions,
  type ModeRevealDocument,
} from './modeRevealTransition';

function fakeDocument(overrides: Partial<ModeRevealDocument> = {}): ModeRevealDocument & { animate: ReturnType<typeof vi.fn> } {
  const animate = vi.fn();
  return {
    startViewTransition: undefined,
    documentElement: { animate, clientHeight: 800, clientWidth: 1280 },
    ...overrides,
    animate,
  } as ModeRevealDocument & { animate: ReturnType<typeof vi.fn> };
}

describe('modeRevealTransition', () => {
  it('applies instantly when View Transitions are unsupported', () => {
    const apply = vi.fn();
    const doc = fakeDocument();
    const outcome = runModeRevealTransition(apply, { doc, origin: { x: 10, y: 10 }, reducedMotion: false });
    expect(outcome).toBe('instant');
    expect(apply).toHaveBeenCalledTimes(1);
  });

  it('skips the view transition under reduced motion even when supported', () => {
    const apply = vi.fn();
    const startViewTransition = vi.fn();
    const doc = fakeDocument({ startViewTransition });
    const outcome = runModeRevealTransition(apply, { doc, origin: { x: 10, y: 10 }, reducedMotion: true });
    expect(outcome).toBe('instant');
    expect(apply).toHaveBeenCalledTimes(1);
    expect(startViewTransition).not.toHaveBeenCalled();
  });

  it('drives a one-shot circle reveal from the click point when supported', async () => {
    const apply = vi.fn();
    const animate = vi.fn();
    const startViewTransition = vi.fn((update: () => void) => {
      update();
      return { ready: Promise.resolve() };
    });
    const doc: ModeRevealDocument = {
      startViewTransition,
      documentElement: { animate, clientHeight: 800, clientWidth: 1280 },
    };
    const outcome = runModeRevealTransition(apply, { doc, origin: { x: 1200, y: 40 }, reducedMotion: false });
    expect(outcome).toBe('view-transition');
    expect(apply).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    const radius = Math.ceil(maxRevealRadius({ x: 1200, y: 40 }, 1280, 800));
    expect(animate).toHaveBeenCalledWith(
      { clipPath: ['circle(0px at 1200px 40px)', `circle(${radius}px at 1200px 40px)`] },
      expect.objectContaining({ duration: MODE_REVEAL_DURATION_MS, pseudoElement: '::view-transition-new(root)' }),
    );
  });

  it('computes the reveal radius to the farthest viewport corner', () => {
    expect(maxRevealRadius({ x: 0, y: 0 }, 300, 400)).toBe(500);
    expect(maxRevealRadius({ x: 300, y: 400 }, 300, 400)).toBe(500);
    expect(supportsViewTransitions(undefined)).toBe(false);
  });
});
