import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DetailBaseline } from './detailArtifactModel';
import { DetailConstructionTable } from './DetailConstructionTable';
import type { DetailOutlineArtifact } from './stageArtifacts';

const baseline: DetailBaseline = {
  characters: [{ identity: '调查员', name: '顾遥' }],
  foreshadows: ['失真童声'],
  relationships: [],
  worldAnchors: ['旧港'],
  worldbuildingDetail: '旧港保存实验档案。',
};

describe('DetailConstructionTable', () => {
  it('keeps duplicate chapter names as separate rows with one active selection', () => {
    const chapters = [chapter(), chapter()];
    const html = renderToStaticMarkup(
      <DetailConstructionTable
        baseline={baseline}
        chapters={chapters}
        deltaBySection={new Map()}
        generating={false}
        liveIndex={1}
        onOpenChapter={() => undefined}
        selectedChapterIndex={1}
      />,
    );

    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(html.match(/完整度 4\/5/g)).toHaveLength(2);
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
