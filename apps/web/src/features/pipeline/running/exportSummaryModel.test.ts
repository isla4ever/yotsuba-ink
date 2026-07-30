import { describe, expect, it } from 'vitest';
import { exportStageSummary } from './exportSummaryModel';
import type { ExportArtifact } from './stageArtifacts';

const artifact: ExportArtifact = {
  bundle_name: '雾港.zip',
  chapters: [{ id: 'chapter-1', title: '第一章' }, { id: 'chapter-2', title: '第二章' }],
  files: [],
  formats: ['md', 'json', 'zip'],
  metadata: { title: '雾港', author: '', version_note: '', bundle_name: '雾港' },
  default_format: 'zip',
  cover_asset: null,
  validation: { chapters: 'ready', cover: 'ready', quality: 'blocked', canon: 'ready' },
  package_ready: false,
};

describe('export stage summary', () => {
  it('derives every metric from the export artifact', () => {
    expect(exportStageSummary(artifact)).toEqual({
      description: '2 章正文已进入交付清单，仍有 2 项校验未就绪。',
      metrics: ['2 章', '2/4 校验', '3 种格式'],
    });
  });

  it('does not treat a legacy partial validation as a ready immutable delivery', () => {
    expect(exportStageSummary({ ...artifact, package_ready: true, validation: { chapters: 'ready' } })).toEqual({
      description: '2 章正文已进入交付清单，仍有 3 项校验未就绪。',
      metrics: ['2 章', '1/4 校验', '3 种格式'],
    });
  });
});
