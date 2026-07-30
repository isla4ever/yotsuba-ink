import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import {
  modelReviewForChapter,
  modelReviewUnavailableText,
  normalizeModelReview,
  showModelReviewSection,
} from './modelReviewPresentation';

const completedPayload = {
  status: 'completed',
  chapter: '第一章',
  chapter_version: 2,
  dimensions: [
    { dimension: '连续性', score: 8.5, evidence: '闸门线索承接上一章', revision_instruction: '' },
    { dimension: '语言质感', score: 6, evidence: '后半段句式重复', revision_instruction: '压缩排比段落' },
  ],
  overall_score: 7.4,
  tension: { score: 7, basis: '对峙升级' },
  voice: { drift: true, notes: '林澈台词偏书面' },
};

describe('model review presentation', () => {
  it('normalizes a completed artifact review with clamped scores and full dimensions', () => {
    const review = normalizeModelReview({ ...completedPayload, dimensions: [...completedPayload.dimensions, { dimension: '模板味', score: 14 }] });
    expect(review?.status).toBe('completed');
    expect(review?.overall_score).toBe(7.4);
    expect(review?.dimensions).toHaveLength(3);
    expect(review?.dimensions?.[2].score).toBe(10);
    expect(review?.voice?.drift).toBe(true);
    expect(normalizeModelReview({ status: 'weird' })).toBeNull();
    expect(normalizeModelReview('text')).toBeNull();
  });

  it('falls back to the model_review_completed event when the artifact has no review', () => {
    const events: RunEvent[] = [{ type: 'model_review_completed', run_id: 'run-1', chapter: '第一章', model_review: completedPayload as never }];
    const review = modelReviewForChapter(undefined, events, '第一章');
    expect(review?.status).toBe('completed');
    expect(review?.dimensions?.[0].dimension).toBe('连续性');
    expect(modelReviewForChapter(undefined, events, '第二章')).toBeNull();
  });

  it('maps model_review_unavailable events to an honest unavailable state', () => {
    const events: RunEvent[] = [{ type: 'model_review_unavailable', run_id: 'run-1', chapter: '第一章', reason: 'provider call failed: connection refused' }];
    const review = modelReviewForChapter(undefined, events, '第一章');
    expect(review?.status).toBe('unavailable');
    expect(review?.error).toContain('connection refused');
  });

  it('translates unavailable reasons into writer-facing language by failure family', () => {
    expect(modelReviewUnavailableText('model_review budget exceeded')).toContain('预算');
    expect(modelReviewUnavailableText('ValidationError: dimensions field required')).toContain('结构检查');
    expect(modelReviewUnavailableText('request timed out')).toContain('超时');
    expect(modelReviewUnavailableText('provider connection refused')).toContain('调用失败');
    expect(modelReviewUnavailableText('')).toContain('暂时不可用');
  });

  it('renders the section only for balanced/deep modes — fast mode gets no disabled shell', () => {
    expect(showModelReviewSection('fast')).toBe(false);
    expect(showModelReviewSection('balanced')).toBe(true);
    expect(showModelReviewSection('deep')).toBe(true);
  });
});
