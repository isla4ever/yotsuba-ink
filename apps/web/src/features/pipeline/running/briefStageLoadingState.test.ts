import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import { briefStageLoadingCopy, briefStageLoadingVisible } from './briefStageLoadingState';

describe('brief stage loading state', () => {
  it('stays visible until Brief reaches a real Graph terminal event', () => {
    const generating = [
      runEvent('node.started', { stage_id: 'brief', node_id: 'brief.generate_candidate' }),
      runEvent('run.started', { stage_id: 'brief', node_id: 'load_run' }),
    ];
    expect(briefStageLoadingVisible('run-1', generating)).toBe(true);
    expect(briefStageLoadingCopy(generating).title).toBe('正在生成创作立项');
    expect(briefStageLoadingVisible('run-1', [
      runEvent('artifact.candidate_ready', { stage_id: 'brief', node_id: 'brief.generate_candidate', payload: {} }),
      ...generating,
    ])).toBe(false);
  });

  it('closes on a real run failure', () => {
    expect(briefStageLoadingVisible('run-1', [
      runEvent('run.failed', { stage_id: 'brief', payload: { message: 'provider unavailable' } }),
    ])).toBe(false);
  });

  it('uses neutral copy before the first server event', () => {
    expect(briefStageLoadingCopy([])).toEqual({ detail: '马上开始', title: '正在建立创作任务' });
  });
});
