import { describe, expect, it } from 'vitest';
import type { StageType } from '../contracts';
import { stageEmptyStateAction, stageEmptyStateHint } from './stageEmptyState';

const allStageTypes: StageType[] = [
  'info_recommend',
  'summary',
  'outline',
  'detail_outline',
  'chapter_text',
  'cover_image',
  'export_artifact',
];

describe('stageEmptyStateHint (A2)', () => {
  it('gives every stage a distinct precondition sentence', () => {
    const hints = allStageTypes.map(stageEmptyStateHint);
    for (const hint of hints) expect(hint.length).toBeGreaterThan(10);
    expect(new Set(hints).size).toBe(allStageTypes.length);
  });

  it('states the upstream gate for key stages', () => {
    expect(stageEmptyStateHint('summary')).toContain('创作立项定稿');
    expect(stageEmptyStateHint('chapter_text')).toContain('章节细纲');
    expect(stageEmptyStateHint('export_artifact')).toContain('封面定稿');
  });
});

describe('stageEmptyStateAction (A2)', () => {
  it('labels the exit CTA by whether a run has started', () => {
    expect(stageEmptyStateAction(true)).toBe('回到创作规划');
    expect(stageEmptyStateAction(false)).toBe('回到创作规划并启动');
  });
});
