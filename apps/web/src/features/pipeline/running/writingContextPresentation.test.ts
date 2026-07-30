import { describe, expect, it } from 'vitest';
import type { ChapterContextPacket } from '../contracts';
import {
  chapterKindLabel,
  chapterOutlinePresentation,
  previousChapterContext,
  trustedCharacterStates,
  trustedContextRules,
  trustedForeshadowLines,
  type DetailChapterContext,
} from './writingContextPresentation';

describe('writing context presentation', () => {
  it('never presents a polluted previous summary as a first-chapter handoff', () => {
    const context = packet({ chapter_kind: 'first', chapter_index: 1, previous_chapter_summary: '错误的第二章摘要' });
    expect(previousChapterContext(context)).toBe('首章，无前章承接。');
    expect(chapterKindLabel(context)).toBe('首章');
  });

  it('only exposes character state that matches the confirmed Info roster', () => {
    const state = {
      'character-1': { name: '苏迟', status: '追查母带' },
      'demo-1': { name: '林雾', status: '演示状态' },
    };
    expect(trustedCharacterStates(state, ['苏迟', '许念'])).toEqual([{ name: '苏迟', status: '追查母带' }]);
    expect(trustedCharacterStates(state, [])).toEqual([]);
  });

  it('shows the causal handoff contract before the previous chapter summary', () => {
    const context = packet({
      chapter_index: 2,
      chapter_kind: 'normal',
      previous_chapter_summary: '林拾带走母带，港务会开始封锁码头。',
      transition_directive: '默认沿上一章结果连续续写，并用封锁行动进入本章。',
    });
    expect(previousChapterContext(context)).toBe('默认沿上一章结果连续续写，并用封锁行动进入本章。\n前章摘要：林拾带走母带，港务会开始封锁码头。');
  });

  it('recovers a readable historical context from the matching detail chapter', () => {
    expect(chapterKindLabel(null, true)).toBe('细纲回溯');
    expect(chapterOutlinePresentation(null, detailChapter)).toContain('苏迟在旧港码头推进：破坏谐振装置');
    expect(chapterOutlinePresentation(null, detailChapter)).toContain('正文交接：公开证据后留下疑声');
  });

  it('filters oversized legacy payloads out of rules and foreshadow lines', () => {
    const context = packet({
      world_rules: ['声音是时间载体', '长'.repeat(300)],
      open_foreshadows: [
        { name: '未署名磁带', status: '投放', note: '卷末出现' },
        { name: `第1章：${'正文'.repeat(180)}`, status: 'open' },
      ],
    });
    expect(trustedContextRules(context)).toEqual(['声音是时间载体']);
    expect(trustedForeshadowLines(context)).toEqual(['未署名磁带 · 投放 · 卷末出现']);
  });
});

const detailChapter: DetailChapterContext = {
  chapter: '第1章', pov: '苏迟', scene: '旧港码头', goal: '破坏谐振装置', entry_state: '记忆污染加剧',
  conflict: '幻象诱导她完成实验', stakes: '许念将在三天后遇害', hook: '收到未署名磁带',
  continuity_notes: '公开证据后留下疑声', fact_reveals: [], wiki_candidates: [], foreshadow: [],
  character_shift: { character: '苏迟', related_to: '', relation: '', pressure: '', motivation: '', change: '', impact: '' },
};

function packet(patch: Partial<ChapterContextPacket>): ChapterContextPacket {
  return {
    chapter: '第1章', chapter_index: 1, chapter_kind: 'first', story_brief: '', summary: '', volume_goal: '',
    chapter_outline: '', previous_chapter_summary: '', previous_volume_ending: '', character_state: {},
    open_foreshadows: [], world_rules: [], ...patch,
  };
}
