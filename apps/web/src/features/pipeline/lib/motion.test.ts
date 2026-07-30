import { describe, expect, it } from 'vitest';
import {
  motionTransition,
  motionTransitionFor,
  routeMotionVariants,
} from './motion';

describe('motion contracts', () => {
  it('removes transition duration for reduced motion', () => {
    expect(motionTransitionFor(true, motionTransition.slow)).toEqual(motionTransition.instant);
    expect(motionTransitionFor(false, motionTransition.slow)).toBe(motionTransition.slow);
  });

  it('uses a direction-neutral route transition for browser history', () => {
    const initial = routeMotionVariants.initial as Record<string, unknown>;
    const exit = routeMotionVariants.exit as Record<string, unknown>;
    expect(initial).toMatchObject({ opacity: 0 });
    expect(initial).not.toHaveProperty('x');
    expect(initial).not.toHaveProperty('y');
    expect(exit).not.toHaveProperty('x');
  });
});
