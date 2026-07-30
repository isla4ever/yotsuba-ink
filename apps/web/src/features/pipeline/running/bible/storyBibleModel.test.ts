import { describe, expect, it } from 'vitest';
import {
  bibleCanonRows,
  bibleCharacterGraph,
  bibleForeshadowRows,
  bibleWorldView,
  normalizeForeshadowStatus,
} from './storyBibleModel';
import { defaultWorkflow } from '../../state/defaultWorkflow';
import type { RunEvent } from '../../contracts';

const infoArtifact = JSON.stringify({
  characters: [
    { name: '沈默', identity: '主角', motivation: '追查记忆真相', tier: 'protagonist', faction: '旧港调查组', faction_stance: 'protagonist_side' },
    { name: '林岚', identity: '搭档', motivation: '守住底线', tier: 'major', faction: '旧港调查组' },
  ],
  relationships: [{ source: '沈默', target: '林岚', relation: '搭档', strength: 0.8, kind: 'ally', polarity: 'positive' }],
});

describe('bibleCharacterGraph', () => {
  it('prefers the latest committed character_graph_updated event', () => {
    const events = [
      {
        type: 'character_graph_updated',
        run_id: 'r1',
        character_graph: { nodes: [{ id: 'c1', name: '沈默', role: '主角', faction: '', status: '' }], edges: [], updated_by: 'summary' },
      },
      { type: 'artifact_approved', run_id: 'r1', node_id: 'info', artifact: infoArtifact },
    ] as RunEvent[];
    const { graph, source } = bibleCharacterGraph(events, defaultWorkflow);
    expect(source).toBe('committed');
    expect(graph.updated_by).toBe('summary');
    expect(graph.nodes).toHaveLength(1);
  });

  it('derives the graph from approved stage artifacts when no committed graph exists', () => {
    const events = [{ type: 'artifact_approved', run_id: 'r1', node_id: 'info', artifact: infoArtifact }] as RunEvent[];
    const { graph, source } = bibleCharacterGraph(events, defaultWorkflow);
    expect(source).toBe('derived');
    expect(graph.nodes.map((node) => node.name)).toEqual(['沈默', '林岚']);
    expect(graph.edges[0]).toMatchObject({ kind: 'ally', polarity: 'positive' });
    expect(graph.factions?.[0]).toMatchObject({ name: '旧港调查组', stance: 'protagonist_side' });
  });

  it('reports the empty state instead of fabricating placeholder data', () => {
    const { graph, source } = bibleCharacterGraph([], defaultWorkflow);
    expect(source).toBe('empty');
    expect(graph.nodes).toHaveLength(0);
    expect(graph.edges).toHaveLength(0);
  });
});

describe('bibleWorldView', () => {
  it('uses committed story bible world rules and labels the writeback source', () => {
    const events = [
      { type: 'story_bible_updated', run_id: 'r1', story_bible: { world_rules: ['记忆改写需要锚点', '死者记忆不可读取'] } },
    ] as RunEvent[];
    const world = bibleWorldView(events);
    expect(world.rules.map((rule) => rule.text)).toEqual(['记忆改写需要锚点', '死者记忆不可读取']);
    expect(world.rules[0].source).toBe('已写回 Story Bible');
  });

  it('falls back to the info baseline and stays empty without any data', () => {
    const events = [
      { type: 'node_completed', run_id: 'r1', node_id: 'info', node_type: 'info_recommend', result: { worldbuilding_detail: '旧港', rules: ['锚点规则'] } },
    ] as RunEvent[];
    expect(bibleWorldView(events).rules).toEqual([{ source: '创作立项基线', text: '锚点规则' }]);
    expect(bibleWorldView([])).toEqual({ anchors: [], rules: [] });
  });
});

describe('bibleForeshadowRows', () => {
  it('reads the committed ledger and sorts unresolved entries before recovered ones', () => {
    const events = [
      {
        type: 'story_bible_updated',
        run_id: 'r1',
        story_bible: {
          foreshadow_ledger: [
            { id: 'f1', name: '怀表', status: '回收', chapter_range: '第1-3章', note: '已兑现', source: 'outline' },
            { id: 'f2', name: '旧照片', status: '投放', chapter_range: '第2章', note: '首次出现', source: 'outline' },
            { id: 'f3', name: '录音带', status: '推进', chapter_range: '第4章', note: '再次提及', source: 'detail' },
          ],
        },
      },
    ] as RunEvent[];
    const rows = bibleForeshadowRows(events);
    expect(rows.map((row) => row.name)).toEqual(['旧照片', '录音带', '怀表']);
    expect(rows[0]).toMatchObject({ open: true, source: '分卷大纲', status: '投放' });
    expect(rows[2]).toMatchObject({ open: false, status: '回收' });
  });

  it('normalizes english status synonyms and defaults unknown values to 投放', () => {
    expect(normalizeForeshadowStatus('recovered')).toBe('回收');
    expect(normalizeForeshadowStatus('advanced')).toBe('推进');
    expect(normalizeForeshadowStatus('deferred')).toBe('延后');
    expect(normalizeForeshadowStatus('???')).toBe('投放');
  });

  it('returns no rows without ledger or artifact data', () => {
    expect(bibleForeshadowRows([])).toEqual([]);
  });
});

describe('bibleCanonRows', () => {
  it('classifies committed facts, supersedes older claims, and highlights pending conflicts first', () => {
    // Events arrive newest-first (reducer prepends).
    const events = [
      {
        type: 'canon_facts_committed',
        run_id: 'r1',
        chapter: '第2章',
        committed: [{ id: 'fact-2', target: '沈默', claim_key: '身份' }],
        pending_conflicts: [
          { id: 'conflict-1', target: '林岚', claim_key: '立场', existing_fact: '林岚是盟友', incoming_fact: '林岚是卧底' },
        ],
      },
      {
        type: 'canon_facts_committed',
        run_id: 'r1',
        chapter: '第1章',
        committed: [
          { id: 'fact-1', target: '沈默', claim_key: '身份' },
          { id: 'fact-0', target: '旧港', claim_key: '规则' },
        ],
        pending_conflicts: [],
      },
    ] as RunEvent[];
    const rows = bibleCanonRows(events);
    expect(rows.map((row) => row.status)).toEqual(['pending', 'active', 'active', 'superseded']);
    expect(rows[0]).toMatchObject({ detail: '林岚是盟友 ↔ 林岚是卧底', target: '林岚' });
    expect(rows[1]).toMatchObject({ chapter: '第2章', key: 'fact-2', status: 'active' });
    expect(rows[3]).toMatchObject({ key: 'fact-1', status: 'superseded' });
  });

  it('returns no rows without canon events', () => {
    expect(bibleCanonRows([])).toEqual([]);
  });
});
