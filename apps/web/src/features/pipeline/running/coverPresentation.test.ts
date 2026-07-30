import { describe, expect, it } from 'vitest';
import { coverAssetFromArtifact, coverDeliveryChecks, coverImageSource, coverQualityPercent, coverReadiness, coverStageSummary, formalCoverCandidateId } from './coverPresentation';
import type { CoverArtifact } from './stageArtifacts';

const artifact: CoverArtifact = {
  brief: '冷峻悬疑封面',
  visual_keywords: ['雾港'],
  composition: '人物背影与港口纵深',
  prompt: 'cinematic harbor cover',
  copy_suggestions: ['雾港回声'],
  candidates: [{
    id: 'cover-a', image_url: '', composition: '中央构图', palette: '冷青', quality_summary: '', asset_status: 'planned', asset_source: 'production',
    generation_key: '', asset_id: '', mime_type: '', width: 0, height: 0, size_bytes: 0, sha256: '', provider_profile_id: '', model: '', attempt: 0, error_code: '', error_message: '',
  }],
  selected_candidate_id: 'cover-a',
  asset_generation: { status: 'planned', total: 1, ready_count: 0, failed_count: 0, provider_profile_id: '', model: '', size: '1024x1536', quality: 'medium', updated_at: '' },
};

describe('cover presentation', () => {
  it('keeps delivery readiness separate from quality scoring', () => {
    const checks = coverDeliveryChecks(artifact);

    expect(checks.filter((check) => check.ready)).toHaveLength(4);
    expect(checks.find((check) => check.key === 'asset')).toMatchObject({ ready: false, detail: '正式候选尚未生成成功的图片' });
    expect(coverQualityPercent(undefined)).toBeNull();
    expect(coverQualityPercent(0.86)).toBe(86);
    expect(coverQualityPercent(72)).toBe(72);
    expect(coverReadiness(artifact)).toMatchObject({ completed: 4, ready: false, total: 5 });
    expect(formalCoverCandidateId(artifact)).toBe('');
  });

  it('extracts only a real selected image asset', () => {
    expect(coverAssetFromArtifact(artifact)).toMatchObject({
      composition: '中央构图',
      imageUrl: '',
      palette: '冷青',
      title: 'cover-a',
    });
    expect(coverImageSource('javascript:alert(1)')).toBe('');
    expect(coverImageSource('data:text/html;base64,PHNjcmlwdD4=')).toBe('');
    expect(coverImageSource('/assets/cover-a.png')).toBe('/assets/cover-a.png');
    expect(formalCoverCandidateId({
      ...artifact,
      candidates: [{ ...artifact.candidates[0], asset_status: 'ready', image_url: '/assets/cover-a.png' }],
    })).toBe('cover-a');
  });

  it('builds the side summary from the artifact and real score only', () => {
    expect(coverStageSummary(artifact, undefined)).toEqual({
      description: '封面方案已生成，图片资产尚未返回。',
      metrics: ['1 个方案', '准备 4/5', '图片待生成'],
    });
    expect(coverStageSummary(artifact, 0.91).metrics).toContain('质量 91%');
  });
});
