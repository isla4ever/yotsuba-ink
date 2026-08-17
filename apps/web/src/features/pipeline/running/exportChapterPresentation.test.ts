import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import { projectExportChapterTitles } from './exportChapterPresentation';

describe('export chapter presentation', () => {
  it('projects accepted chapter titles without exposing immutable version ids', () => {
    const events = [
      runEvent('artifact.committed', {
        stage_id: 'text',
        chapter_id: 'chapter-1',
        payload_ref: 'chapter-1-v2-accepted',
        payload: {
          chapter_id: 'chapter-1',
          version_id: 'chapter-1-v2-accepted',
          title: '午夜来电',
          content: '正文',
          author_status: 'accepted',
        },
      }),
      runEvent('artifact.committed', {
        stage_id: 'detail',
        payload: {
          chapters: [
            detailChapter('chapter-1', '午夜初响'),
            detailChapter('chapter-2', '旧案回声'),
          ],
        },
      }),
    ];

    expect(projectExportChapterTitles(events, [
      'chapter-1-v2-accepted',
      'chapter-2-v1-accepted',
      'chapter-3-v1-accepted',
    ])).toEqual(['午夜来电', '旧案回声', '第 3 章']);
  });
});

function detailChapter(ref: string, title: string) {
  return {
    ref,
    volume_ref: 'volume-1',
    title,
    target_characters: 2_500,
    turn_refs: ['turn-1'],
    purpose: '推动调查',
    pov: 'subject-1',
    cast_ids: ['subject-1'],
    scenes: [{ place: '调度中心', objective: '核对来电', conflict: '时间不足', turn: '发现日期异常', result: '决定追查' }],
    handoff: '下一章继续核对旧案',
  };
}
