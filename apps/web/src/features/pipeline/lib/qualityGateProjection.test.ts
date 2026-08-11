import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { chapterCapacitySummary, latestChapterCapacity } from './qualityGateProjection';

describe('quality gate projection', () => {
  it('projects the latest deterministic chapter capacity sidecar', () => {
    const capacity = latestChapterCapacity([
      decisionEvent(1, 1666, 'within_soft'),
      decisionEvent(2, 1138, 'hard_underflow'),
    ]);

    expect(capacity).toMatchObject({
      visibleChars: 1138,
      targetChars: 2000,
      status: 'hard_underflow',
    });
    expect(chapterCapacitySummary(capacity!)).toBe('低于硬下限 · 1138 / 2000 字 · 硬区间 1300-3000');
  });

  it('ignores decision payloads without a valid capacity contract', () => {
    const event = decisionEvent(1, 1666, 'within_soft');
    event.payload = { reason: { capacity: { status: 'unknown' } } };

    expect(latestChapterCapacity([event])).toBeUndefined();
  });
});

function decisionEvent(
  sequence: number,
  visibleChars: number,
  status: 'hard_underflow' | 'within_soft',
): RunEvent {
  return {
    event_id: `decision-${sequence}`,
    sequence,
    occurred_at: '2026-08-11T00:00:00Z',
    run_id: 'run-1',
    thread_id: 'run-1',
    type: 'decision.required',
    stage_id: 'text',
    node_id: 'text.author_decision',
    chapter_id: 'chapter-1',
    status: 'awaiting_decision',
    payload: {
      reason: {
        capacity: {
          counting_standard: 'cjk-visible-chars-v1',
          visible_chars: visibleChars,
          target_chars: 2000,
          soft_min_chars: 1600,
          soft_max_chars: 2400,
          hard_min_chars: 1300,
          hard_max_chars: 3000,
          status,
        },
      },
    },
    payload_ref: '',
    checkpoint_id: '',
  };
}
