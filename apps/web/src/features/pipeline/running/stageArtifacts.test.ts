import { describe, expect, it } from 'vitest';
import { coverArtifact, detailArtifact, exportArtifact, outlineArtifact } from './stageArtifacts';

describe('structured stage artifact editing', () => {
  it('preserves relationship semantics and Wiki claim keys from backend artifacts', () => {
    const outline = outlineArtifact(JSON.stringify({ volumes: [{
      character_progression: [{ character: '林澈', related_to: '苏闻', relation: '调查同盟', kind: 'ally', polarity: 'complex', strength: 0.72 }],
    }] }));
    const detail = detailArtifact(JSON.stringify({ chapters: [{
      character_shift: { character: '林澈', kind: 'ally', polarity: 'complex', strength: 0.66 },
      wiki_candidates: [{ title: '雾钟', fact: '只记录既有声纹', source_anchor: '雾钟', claim_key: 'recording_rule' }],
    }] }));

    expect(outline.volumes[0].character_progression[0]).toMatchObject({ kind: 'ally', polarity: 'complex', strength: 0.72 });
    expect(detail.chapters[0].character_shift).toMatchObject({ kind: 'ally', polarity: 'complex', strength: 0.66 });
    expect(detail.chapters[0].wiki_candidates[0].claim_key).toBe('recording_rule');
  });
});

describe('cover artifact view model', () => {
  it('normalizes legacy candidates that omit image asset fields', () => {
    const artifact = coverArtifact(JSON.stringify({
      brief: '冷峻悬疑封面',
      selected_candidate_id: 'cover-1',
      candidates: [{ id: 'cover-1', composition: '雾中码头' }],
    }));

    expect(artifact).toMatchObject({
      candidates: [{
        id: 'cover-1',
        image_url: '',
        composition: '雾中码头',
        palette: '',
        quality_summary: '',
      }],
    });
  });
});

describe('export artifact view model', () => {
  it('preserves server export metadata without bypassing the four delivery gates', () => {
    const artifact = exportArtifact(JSON.stringify({
      chapters: [{ id: 'chapter-1', title: '第一章' }],
      formats: ['zip', 'md'],
      metadata: {
        title: '雾港',
        author: '林舟',
        bundle_name: '雾港投稿版',
        version_note: '编辑定稿版',
      },
      package_status: { kind: 'zip', name: 'server-fallback', ready: true },
      validation: { chapters: 'ready' },
    }));

    expect(artifact).toMatchObject({
      formats: ['zip', 'md'],
      default_format: 'zip',
      metadata: {
        title: '雾港',
        author: '林舟',
        bundle_name: '雾港投稿版',
        version_note: '编辑定稿版',
      },
      package_ready: false,
    });
  });

  it('marks the package ready only when the cover asset and all delivery gates are ready', () => {
    const artifact = exportArtifact(JSON.stringify({
      chapters: [{ id: 'chapter-1', title: '第一章' }],
      cover_asset: {
        candidate_id: 'cover-1',
        asset_id: 'asset-1',
        sha256: 'abc123',
        mime_type: 'image/png',
        width: 1600,
        height: 2400,
        size_bytes: 1024,
        image_url: '/api/assets/asset-1',
      },
      package_status: { kind: 'zip', name: 'novel.zip', ready: true },
      validation: { chapters: 'ready', cover: 'ready', quality: 'ready', canon: 'ready' },
    }));

    expect(artifact.package_ready).toBe(true);
  });

  it('uses stable export defaults when optional server fields are absent', () => {
    expect(exportArtifact('{}')).toMatchObject({
      bundle_name: 'novel-export',
      formats: ['md', 'json', 'zip'],
      default_format: 'md',
      metadata: { title: '', author: '', bundle_name: 'novel-export', version_note: '' },
      package_ready: false,
    });
  });
});
