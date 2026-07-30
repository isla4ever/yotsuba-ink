import { describe, expect, it } from 'vitest';
import { OUTLINE_BEAT_DEFINITIONS } from './outlinePresentation';

describe('outline presentation', () => {
  it('keeps the approved five-beat sequence stable', () => {
    expect(OUTLINE_BEAT_DEFINITIONS.map((beat) => beat.key)).toEqual([
      'opening',
      'development',
      'midpoint',
      'climax',
      'resolution',
    ]);
  });
});
