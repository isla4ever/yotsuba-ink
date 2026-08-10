import { describe, expect, it } from 'vitest';
import { stageRuntimeLayout } from './stageRuntimeLayout';

describe('stageRuntimeLayout', () => {
  it('keeps cross-stage systems compact on manuscript stages', () => {
    expect(stageRuntimeLayout.characters).toEqual({ primary: [], compact: ['character'] });
    expect(stageRuntimeLayout.summary).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.outline).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.detail).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.text.compact).toContain('wiki');
  });

  it('does not duplicate delivery summaries outside cover and export artifacts', () => {
    expect(stageRuntimeLayout.cover).toEqual({ primary: [], compact: [] });
    expect(stageRuntimeLayout.export).toEqual({ primary: [], compact: [] });
  });
});
