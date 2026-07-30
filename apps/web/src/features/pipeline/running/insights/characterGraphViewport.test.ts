import { describe, expect, it } from 'vitest';
import { characterGraphViewport } from './characterGraphViewport';

describe('characterGraphViewport', () => {
  it('caps an inflated mobile observation to a compact viewport preview', () => {
    expect(characterGraphViewport({
      containerHeight: 283_294,
      containerWidth: 344,
      viewportHeight: 844,
      viewportWidth: 390,
    })).toEqual({ height: 337, width: 344 });
  });

  it('keeps a useful minimum when the preview has not laid out yet', () => {
    expect(characterGraphViewport({
      containerHeight: 0,
      containerWidth: 156,
      viewportHeight: 640,
      viewportWidth: 320,
    })).toEqual({ height: 256, width: 180 });
  });

  it('allows a larger desktop graph without exceeding the viewport budget', () => {
    expect(characterGraphViewport({
      containerHeight: 1_200,
      containerWidth: 1_018,
      viewportHeight: 1_100,
      viewportWidth: 1_728,
    })).toEqual({ height: 760, width: 1_018 });
  });
});
