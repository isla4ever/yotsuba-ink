import { describe, expect, it } from 'vitest';
import {
  exportPackageName,
  exportSelectionsEqual,
  freezeExportSelection,
  toggleExportChapter,
  type ExportSelectionSnapshot,
} from './exportSelectionModel';

const selection: ExportSelectionSnapshot = {
  chapter_ids: ['chapter-1', 'chapter-2'],
  format: 'zip',
  metadata: { author: ' 林舟 ', bundle_name: ' 雾港终稿.zip ', title: ' 雾港 ', version_note: ' 第一版 ' },
};

describe('frozen export selection', () => {
  it('copies and normalizes every value used by an export request', () => {
    const source = { ...selection, chapter_ids: [...selection.chapter_ids] };
    const frozen = freezeExportSelection(source);
    source.chapter_ids.push('chapter-3');
    expect(frozen).toEqual({
      chapter_ids: ['chapter-1', 'chapter-2'],
      format: 'zip',
      metadata: { author: '林舟', bundle_name: '雾港终稿', title: '雾港', version_note: '第一版' },
    });
  });

  it('treats chapter order, format, and metadata as receipt-bound inputs', () => {
    const frozen = freezeExportSelection(selection);
    expect(exportSelectionsEqual(frozen, { ...frozen, chapter_ids: [...frozen.chapter_ids].reverse() })).toBe(false);
    expect(exportSelectionsEqual(frozen, { ...frozen, format: 'json' })).toBe(false);
    expect(exportSelectionsEqual(frozen, { ...frozen, metadata: { ...frozen.metadata, author: '他人' } })).toBe(false);
  });

  it('derives the preview filename from the frozen metadata and format', () => {
    expect(exportPackageName(freezeExportSelection(selection), 'fallback.md')).toBe('雾港终稿.zip');
  });

  it('keeps toggled chapters in story order', () => {
    expect(toggleExportChapter(
      ['chapter-1', 'chapter-2', 'chapter-3'],
      ['chapter-1', 'chapter-3'],
      'chapter-2',
    )).toEqual(['chapter-1', 'chapter-2', 'chapter-3']);
  });
});
