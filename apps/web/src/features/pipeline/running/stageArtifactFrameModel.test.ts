import { describe, expect, it } from 'vitest';
import { stageArtifactFrameByType } from './stageArtifactFrameModel';

describe('stage artifact frame model', () => {
  it('projects every Phase 27 stage from its single Artifact contract', () => {
    expect(Object.keys(stageArtifactFrameByType)).toEqual([
      'brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export',
    ]);
    expect(stageArtifactFrameByType.cast.artifact).toBe('人物圣经');
    expect(stageArtifactFrameByType.text.writeback).toBe('保存为章节版本');
    expect(stageArtifactFrameByType.export.downstream).toBe('交付完成');
  });

  it('keeps runtime-only evidence outside the Artifact frame', () => {
    Object.values(stageArtifactFrameByType).forEach((frame) => {
      expect(JSON.stringify(frame)).not.toMatch(/checkpoint|review|receipt|SSE/i);
      expect(JSON.stringify(frame)).not.toMatch(/ArtifactStore|ChapterStore|ExportStore/);
    });
  });
});
