import { describe, expect, it } from 'vitest';
import type { RunHistoryItem } from '../contracts';
import { mergeRunHistory } from './useRunHistory';

describe('run history merge', () => {
  it('moves an updated run to the front without duplicates', () => {
    const current = [item('run-a', '旧记录'), item('run-b', '其他记录')];
    const merged = mergeRunHistory(current, item('run-a', '新记录'));

    expect(merged.map((entry) => entry.run_id)).toEqual(['run-a', 'run-b']);
    expect(merged[0].title).toBe('新记录');
  });

  it('keeps a bounded set of recent runs', () => {
    const current = Array.from({ length: 24 }, (_, index) => item(`run-${index}`, `${index}`));
    const merged = mergeRunHistory(current, item('new-run', '最新'));

    expect(merged).toHaveLength(24);
    expect(merged[0].run_id).toBe('new-run');
    expect(merged.some((entry) => entry.run_id === 'run-23')).toBe(false);
  });
});

function item(run_id: string, title: string): RunHistoryItem {
  return {
    run_id,
    project_id: 'project',
    title,
    quality_mode: 'balanced',
    updated_at: '2026-07-16T00:00:00.000Z',
    created_at: '2026-07-16T00:00:00.000Z',
    completed_at: '',
    current_stage: { id: 'summary', label: '全书梗概', type: 'summary' },
    completed_stage_ids: [],
    status: 'completed',
    words: 100,
    total_tokens: 200,
    estimated_cost_usd: 0.01,
    summary: title,
    can_resume: false,
    recovery_required: false,
    latest_snapshot_id: '',
    export_ready: false,
    export_count: 0,
    latest_export: null,
    state_revision: 0,
  };
}
