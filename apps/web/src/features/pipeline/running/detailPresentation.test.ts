import { describe, expect, it } from 'vitest';
import { detailClueSummary, detailFactSummary, detailMemoryCounts } from './detailPresentation';
import type { DetailOutlineArtifact } from './stageArtifacts';

describe('detail presentation', () => {
  it('derives readable chapter summaries and real writeback counts', () => {
    const artifact: DetailOutlineArtifact = { chapters: [chapter()], coverage: { complete: true, generated: 1, planned: 1 } };

    expect(detailFactSummary(artifact.chapters[0])).toBe('失踪名单');
    expect(detailClueSummary(artifact.chapters[0])).toBe('失真童声 · 回收');
    expect(detailMemoryCounts(artifact)).toEqual({ character: 1, clue: 1, fact: 2 });
  });
});

function chapter(): DetailOutlineArtifact['chapters'][number] {
  return {
    chapter: '第一章',
    character_shift: { character: '顾遥', related_to: '', relation: '', pressure: '证据将消失', motivation: '追查旧案', change: '选择合作', impact: '进入下一章' },
    conflict: '巡检队封锁退路',
    continuity_notes: '母带交给林澈',
    entry_state: '独自进入航道',
    fact_reveals: [{ anchor: '旧港', fact: '航道通向档案室', impact: '获得入口' }],
    foreshadow: [{ name: '失真童声', note: '确认归属', status: '回收' }],
    goal: '取得母带',
    hook: '名单出现本人',
    pov: '顾遥',
    scene: '旧航道',
    stakes: '身份暴露',
    wiki_candidates: [{ fact: '名单仍在更新', source_anchor: '旧港', title: '失踪名单' }],
  };
}
