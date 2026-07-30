import { describe, expect, it } from 'vitest';
import type { ChapterQualityRepairTarget } from '../contracts';
import { chapterRepairSelection, chapterRevisionSignature, chapterSelection } from './chapterSelectionModel';

describe('chapter selection model', () => {
  it('uses textarea UTF-16 offsets without shifting emoji selections', () => {
    const content = '开场😀林澈保留母带，结尾不变。';
    const start = content.indexOf('林澈');
    const end = start + '林澈保留母带'.length;
    expect(chapterSelection(content, start, end)).toEqual({
      start,
      end,
      text: '林澈保留母带',
    });
  });

  it('rejects empty and oversized selections', () => {
    expect(chapterSelection('正文', 1, 1)).toBeNull();
    expect(chapterSelection(' '.repeat(10), 0, 10)).toBeNull();
    expect(chapterSelection('字'.repeat(6001), 0, 6001)).toBeNull();
  });

  it('changes the edit signature when the chapter content changes', async () => {
    const base = {
      id: 'chapter-1',
      version: 1,
      content: '原始正文',
      summary: '摘要',
      summary_dirty: false,
    };
    const first = await chapterRevisionSignature(base as never);
    const second = await chapterRevisionSignature({ ...base, content: '新正文' } as never);
    expect(first).toHaveLength(64);
    expect(second).not.toBe(first);
  });

  it('accepts only a repair target bound to the current chapter version and signature', async () => {
    const chapter = {
      id: 'chapter-1',
      version: 3,
      content: '开场😀林澈保留母带，结尾不变。',
      summary: '林澈保留母带。',
      summary_dirty: false,
    };
    const start = chapter.content.indexOf('林澈');
    const target: ChapterQualityRepairTarget = {
      finding_id: 'text-structure',
      chapter_id: chapter.id,
      chapter: '第1章',
      artifact_signature: await chapterRevisionSignature(chapter as never),
      chapter_version: chapter.version,
      dimension: 'structure',
      message: '正文结构待补足',
      instruction: '补足动作因果。',
      operation: 'expand',
      start,
      end: start + '林澈保留母带'.length,
      selected_text: '林澈保留母带',
      locatable: true,
    };

    await expect(chapterRepairSelection(chapter as never, target)).resolves.toEqual({
      start: target.start,
      end: target.end,
      text: target.selected_text,
    });
    await expect(chapterRepairSelection({ ...chapter, version: 4 } as never, target)).resolves.toBeNull();
    await expect(chapterRepairSelection({ ...chapter, content: `${chapter.content}新增` } as never, target)).resolves.toBeNull();
  });
});
