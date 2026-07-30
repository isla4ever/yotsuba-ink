import { describe, expect, it } from 'vitest';
import { detailChapterReadiness, type DetailBaseline } from './detailArtifactModel';
import { buildCoverageCells, coverageCellDescription, coverageSummary } from './detailCoverageModel';
import type { DetailChapter } from './detailPresentation';

const baseline: DetailBaseline = {
  characters: [
    { name: '林澈', identity: '主角' },
    { name: '顾遥', identity: '搭档' },
  ],
  relationships: [{ source: '林澈', target: '顾遥', relation: '搭档' }],
  worldbuildingDetail: '旧港的声纹闸门由潮汐供能。',
  worldAnchors: ['声纹闸门'],
  foreshadows: ['失真童声'],
};

function completeChapter(name: string): DetailChapter {
  return {
    chapter: name,
    pov: '林澈',
    scene: '旧港闸门',
    goal: '找到母带来源',
    entry_state: '深夜抵达',
    conflict: '闸门拒绝声纹',
    stakes: '潮水上涨',
    hook: '闸门里传出童声',
    continuity_notes: '承接上一章的来信',
    character_shift: {
      character: '林澈', related_to: '顾遥', relation: '搭档', pressure: '被质疑',
      motivation: '证明母带真实', change: '开始信任顾遥', impact: '二人协作',
    },
    fact_reveals: [{ anchor: '声纹闸门', fact: '闸门只认潮汐节律', impact: '必须等退潮' }],
    wiki_candidates: [{ title: '声纹闸门', fact: '由潮汐供能', source_anchor: '声纹闸门' }],
    foreshadow: [{ name: '失真童声', status: '投放', note: '声源不明' }],
  };
}

function partialChapter(name: string): DetailChapter {
  const chapter = completeChapter(name);
  return {
    ...chapter,
    character_shift: { ...chapter.character_shift, pressure: '', motivation: '', change: '', impact: '' },
    foreshadow: [],
  };
}

describe('detail coverage heat strip model', () => {
  it('derives every cell from detailChapterReadiness so the strip always matches the construction table badge', () => {
    const chapters = [completeChapter('第一章'), partialChapter('第二章')];
    const cells = buildCoverageCells(chapters, baseline);
    const chapterNames = chapters.map((chapter) => chapter.chapter);
    chapters.forEach((chapter, index) => {
      const readiness = detailChapterReadiness(chapter, baseline, index, chapterNames);
      expect(cells[index].completed).toBe(readiness.completed);
      expect(cells[index].total).toBe(readiness.total);
    });
    expect(cells[0].completed).toBe(5);
    expect(cells[0].total).toBe(5);
    expect(cells[1].completed).toBe(3);
  });

  it('lists the missing check groups without the chapter label prefix', () => {
    const cells = buildCoverageCells([partialChapter('第二章')], baseline);
    expect(cells[0].missingGroups).toEqual(['人物变化', '伏笔动作']);
    expect(coverageCellDescription(cells[0])).toBe('第二章 覆盖 3/5：缺人物变化、伏笔动作');
    expect(coverageCellDescription(cells[0], true)).toBe('第二章 新版结构覆盖 3/5：缺人物变化、伏笔动作');
  });

  it('confirms constructability when a chapter closes all five groups', () => {
    const cells = buildCoverageCells([completeChapter('第一章')], baseline);
    expect(cells[0].missingGroups).toEqual([]);
    expect(coverageCellDescription(cells[0])).toContain('覆盖 5/5');
    expect(coverageCellDescription(cells[0])).toContain('可施工');
    expect(coverageSummary(cells)).toBe('全部 1 章五组检查 5/5，可进入正文施工');
    expect(coverageSummary(cells, true)).toBe('历史稿已完成 · 新版结构覆盖 1/1');
  });

  it('returns no cells (missing state) when there is no chapter data', () => {
    expect(buildCoverageCells([], baseline)).toEqual([]);
    expect(coverageSummary(buildCoverageCells([completeChapter('第一章'), partialChapter('第二章')], baseline))).toBe('1/2 章可施工');
  });
});
