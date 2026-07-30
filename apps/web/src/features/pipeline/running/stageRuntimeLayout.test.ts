import { describe, expect, it } from 'vitest';
import { stageRuntimeLayout } from './stageRuntimeLayout';

describe('stageRuntimeLayout', () => {
  it('keeps cross-stage systems compact on manuscript stages', () => {
    expect(stageRuntimeLayout.summary).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.outline).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'quality'],
    });
    expect(stageRuntimeLayout.detail_outline).toEqual({
      primary: [],
      compact: ['character', 'worldbuilding', 'wiki', 'quality'],
    });
  });

  it('does not duplicate delivery summaries outside cover and export artifacts', () => {
    expect(stageRuntimeLayout.cover_image).toEqual({ primary: [], compact: [] });
    expect(stageRuntimeLayout.export_artifact).toEqual({ primary: [], compact: [] });
  });
});
