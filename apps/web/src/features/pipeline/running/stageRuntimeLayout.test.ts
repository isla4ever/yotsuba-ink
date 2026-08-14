import { describe, expect, it } from 'vitest';
import { stageRuntimeLayout } from './stageRuntimeLayout';

describe('stageRuntimeLayout', () => {
  it('keeps cross-stage systems compact on manuscript stages', () => {
    expect(stageRuntimeLayout.cast).toEqual({ primary: [], compact: [] });
    expect(stageRuntimeLayout.spine).toEqual({
      primary: [],
      compact: ['worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.volumes).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.detail).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.text.compact).toEqual(['contextManifest', 'quality', 'wiki', 'character', 'worldbuilding']);
  });

  it('does not duplicate delivery summaries outside cover and export artifacts', () => {
    expect(stageRuntimeLayout.cover).toEqual({ primary: [], compact: [] });
    expect(stageRuntimeLayout.export).toEqual({ primary: [], compact: [] });
  });
});
