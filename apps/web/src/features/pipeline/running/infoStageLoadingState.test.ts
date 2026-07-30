import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { infoStageLoadingCopy, infoStageLoadingVisible } from './infoStageLoadingState';

describe('info stage loading state', () => {
  it('stays visible until the Info artifact reaches a real terminal event', () => {
    const generating = events(
      { type: 'node_started', node_id: 'info' },
      { type: 'run_started' },
    );

    expect(infoStageLoadingVisible('run-1', generating)).toBe(true);
    expect(infoStageLoadingCopy(generating).title).toBe('正在生成小说信息推荐');
    expect(infoStageLoadingVisible('run-1', events(
      { type: 'node_completed', node_id: 'info' },
      ...generating,
    ))).toBe(false);
  });

  it('closes on a real run failure instead of waiting for a timer', () => {
    expect(infoStageLoadingVisible('run-1', events(
      { type: 'run_error', error: 'provider unavailable' },
      { type: 'run_started' },
    ))).toBe(false);
  });

  it('uses neutral copy before the first server event', () => {
    expect(infoStageLoadingCopy([])).toEqual({
      detail: '马上开始',
      title: '正在建立创作任务',
    });
  });
});

function events(...items: Array<Partial<RunEvent> & Pick<RunEvent, 'type'>>) {
  return items as RunEvent[];
}
