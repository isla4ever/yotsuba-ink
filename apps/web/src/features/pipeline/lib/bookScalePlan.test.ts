import { describe, expect, it } from 'vitest';
import cases from '../../../../test-fixtures/book-scale-contract-cases.json';
import type { BookScaleTargetMode } from '../contracts';
import { buildBookScalePlan } from './bookScalePlan';

describe('book scale preview parity', () => {
  it.each(cases)('matches the server contract fixture: $id', (contractCase) => {
    const plan = buildBookScalePlan(
      contractCase.target_mode as BookScaleTargetMode,
      contractCase.target_value,
    );
    const expected = contractCase.expected;

    expect(plan.total_chars).toBe(expected.total_chars);
    expect(plan.total_chapters).toBe(expected.total_chapters);
    expect(plan.volume_count).toBe(expected.volume_count);
    expect(plan.chapters_per_volume).toEqual(expected.chapters_per_volume);
    expect(plan.chapter_target_chars).toBe(expected.chapter_target_chars);
    expect([plan.chapter_soft_min_chars, plan.chapter_soft_max_chars]).toEqual(expected.chapter_soft_chars);
    expect([plan.chapter_hard_min_chars, plan.chapter_hard_max_chars]).toEqual(expected.chapter_hard_chars);
    expect([plan.book_soft_min_chars, plan.book_soft_max_chars]).toEqual(expected.book_soft_chars);
    expect(plan.volumes.map((volume) => volume.target_chars)).toEqual(expected.volume_target_chars);
  });
});
