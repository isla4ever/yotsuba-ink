import { describe, expect, it } from 'vitest';
import type { StageType } from '../contracts';
import { stageEmptyStateAction, stageEmptyStateHint } from './stageEmptyState';

const allStageTypes: StageType[] = [
  'info',
  'characters',
  'summary',
  'outline',
  'detail',
  'text',
  'cover',
  'export',
];

describe('stageEmptyStateHint (A2)', () => {
  it('gives every stage a distinct precondition sentence', () => {
    const hints = allStageTypes.map(stageEmptyStateHint);
    for (const hint of hints) expect(hint.length).toBeGreaterThan(10);
    expect(new Set(hints).size).toBe(allStageTypes.length);
  });

  it('states the upstream gate for key stages', () => {
    expect(stageEmptyStateHint('summary')).toContain('人物圣经冻结');
    expect(stageEmptyStateHint('text')).toContain('章节施工图冻结');
    expect(stageEmptyStateHint('export')).toContain('封面资产选定');
  });
});

describe('stageEmptyStateAction (A2)', () => {
  it('labels the exit CTA by whether a run has started', () => {
    expect(stageEmptyStateAction(true)).toBe('回到创作规划');
    expect(stageEmptyStateAction(false)).toBe('回到创作规划并启动');
  });
});
