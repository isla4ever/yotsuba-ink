import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { latestResult, stageQualityScore, statusText } from './stageRunUtils';

describe('stage run quality score', () => {
  it('uses a real stage quality event instead of the configured threshold', () => {
    const events: RunEvent[] = [
      { type: 'quality_check_completed', run_id: 'run', node_id: 'summary', quality_report: { node_id: 'summary', node_type: 'summary', label: '梗概', score: 0.91, passed: true, mode: 'deep', findings: [], constraint_hits: [], revision_required: false } },
    ];

    expect(stageQualityScore(events, 'summary')).toBe(0.91);
    expect(stageQualityScore(events, 'cover')).toBeNull();
  });

  it('normalizes a real asset progress percentage', () => {
    expect(stageQualityScore([{ type: 'asset_progress_updated', run_id: 'run', node_id: 'cover', score: 84 }], 'cover')).toBe(0.84);
  });

  it('does not call a Cover lifecycle complete before its selected image asset is ready', () => {
    const events = [{
      type: 'node_completed',
      run_id: 'run',
      node_id: 'cover',
      result: { brief: '简报', prompt: 'prompt', candidates: [{ id: 'cover-1', image_url: '' }], selected_candidate_id: 'cover-1' },
    }] as RunEvent[];
    expect(statusText({ id: 'cover', type: 'cover_image' }, events)).toBe('待完善');
  });

  it('uses the persisted snapshot artifact when recovering a historical stage', () => {
    const artifact = { full_synopsis: '恢复后的梗概' };
    const events = [
      { artifact, node_id: 'summary', run_id: 'run', type: 'artifact_validated' },
      { node_id: 'summary', result: { full_synopsis: '旧事件梗概' }, run_id: 'run', type: 'node_completed' },
    ] as RunEvent[];

    expect(latestResult(events, 'summary')).toBe(JSON.stringify(artifact));
  });
});
