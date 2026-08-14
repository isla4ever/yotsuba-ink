import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../../contracts';
import { blockingCount, chapterReviewLanes } from './chapterReviewFindings';

function reviewEvent(
  sequence: number,
  versionId: string,
  role: string,
  findings: unknown[],
  type: RunEvent['type'] = 'review.completed',
): RunEvent {
  return {
    event_id: `run-1:chapter-1:review:${versionId}:${role}:completed`,
    sequence,
    occurred_at: '2026-08-13T19:00:00Z',
    run_id: 'run-1',
    thread_id: 'run-1',
    type,
    stage_id: 'text',
    node_id: 'text.review_chapter',
    chapter_id: 'chapter-1',
    status: type === 'review.completed' ? 'completed' : 'unavailable',
    payload: { role, required: true, available: type === 'review.completed', findings },
  } as unknown as RunEvent;
}

const blocking = [{ claim: '早于出场窗口', code: 'early_appearance', evidence: '王建国走进来', severity: 'blocking' }];

describe('chapterReviewLanes', () => {
  it('keeps only the newest chapter version after a regeneration', () => {
    const lanes = chapterReviewLanes(
      [
        reviewEvent(1, 'chapter-1-v1', 'character', blocking),
        reviewEvent(2, 'chapter-1-v1', 'continuity', []),
        reviewEvent(3, 'chapter-1-v2', 'character', []),
        reviewEvent(4, 'chapter-1-v2', 'continuity', []),
      ],
      'chapter-1',
    );
    expect(lanes.map((lane) => lane.role).sort()).toEqual(['character', 'continuity']);
    expect(blockingCount(lanes)).toBe(0);
  });

  it('reads verdicts in sequence order regardless of arrival order', () => {
    const lanes = chapterReviewLanes(
      [reviewEvent(4, 'chapter-1-v2', 'character', []), reviewEvent(1, 'chapter-1-v1', 'character', blocking)],
      'chapter-1',
    );
    expect(blockingCount(lanes)).toBe(0);
  });

  it('marks a required lane that never produced a verdict', () => {
    const [lane] = chapterReviewLanes(
      [reviewEvent(1, 'chapter-1-v1', 'character', [], 'review.unavailable')],
      'chapter-1',
    );
    expect(lane.available).toBe(false);
    expect(lane.required).toBe(true);
  });
});
