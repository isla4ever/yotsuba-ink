import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import { infoStageLoadingCopy, infoStageLoadingVisible } from './infoStageLoadingState';

describe('info stage loading state', () => {
  it('stays visible until Info reaches a real Graph terminal event', () => {
    const generating = [
      runEvent('node.started', { stage_id: 'info', node_id: 'info.generate_candidate' }),
      runEvent('run.started', { stage_id: 'info', node_id: 'load_run' }),
    ];
    expect(infoStageLoadingVisible('run-1', generating)).toBe(true);
    expect(infoStageLoadingCopy(generating).title).toBe('正在生成创作立项');
    expect(infoStageLoadingVisible('run-1', [
      runEvent('artifact.candidate_ready', { stage_id: 'info', node_id: 'info.generate_candidate', payload: {} }),
      ...generating,
    ])).toBe(false);
  });

  it('closes on a real run failure', () => {
    expect(infoStageLoadingVisible('run-1', [
      runEvent('run.failed', { stage_id: 'info', payload: { message: 'provider unavailable' } }),
    ])).toBe(false);
  });

  it('uses neutral copy before the first server event', () => {
    expect(infoStageLoadingCopy([])).toEqual({ detail: '马上开始', title: '正在建立创作任务' });
  });
});
