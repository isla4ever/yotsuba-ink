import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { runtimeArtifactProjection } from './runtimeArtifactProjection';

const brief = JSON.stringify({
  title: '雾港母带',
  premise: '调查一卷会改写记忆的失踪母带。',
  promise: '母带来源会被查明。',
  world_rules: ['广播只会覆盖被明确标记的记忆'],
  theme: '公开真相是否值得失去私人记忆？',
  ending_promise: '母带来源会在终章公开。',
  voice: '第三人称有限视角，过去时，以听觉细节为主。',
  length_envelope: { word_target_soft: 80000 },
});

const cast = JSON.stringify({
  subjects: [{ id: 'subject-lin', name: '林默', kind: 'protagonist', function: '承担真相调查', background: '旧港公共档案修复师，曾参与事故母带的初次修复。', conflict_history: '她亲眼见过事故母带被替换，却因证据不足保持沉默。', present_stakes: '若证据失效，她会失去职业资格和追查母亲去向的最后机会。', temperament: '受压时先核对记录，再逼迫对方作出明确选择。', speech_style: '短句，少下判断，习惯复述记录原文。', drive: '找到母带', change: '接受共同记忆', debut: 'chapter:1', limits: ['不得伪造证据'], demand_refs: ['demand-investigator'] }],
  relations: [],
});

const detail = JSON.stringify({
  chapters: [{
    ref: 'chapter-1',
    volume_ref: 'volume-1',
    title: '旧港回声',
    target_characters: 3000,
    turn_refs: ['turn-1'],
    purpose: '取得第一份证据',
    pov: 'subject-lin',
    cast_ids: ['subject-lin'],
    scenes: [
      { place: '旧港仓库', objective: '取回母带', conflict: '仓库被封锁', turn: '发现一份副本', result: '带走副本' },
      { place: '旧潮道', objective: '离开封锁区', conflict: '追兵逼近', turn: '找到暗门', result: '进入潮道' },
    ],
    handoff: '追兵开始接近',
  }],
});

describe('runtimeArtifactProjection', () => {
  it('projects only Phase 27 artifacts and the latest stable writeback event', () => {
    const events: RunEvent[] = [
      runEvent('writeback.committed', { run_id: 'run-1', stage_id: 'detail', sequence: 4, payload: { transaction_id: 'tx-old' } }),
      runEvent('writeback.queued', { run_id: 'run-1', stage_id: 'detail', sequence: 5, payload: { transaction_id: 'tx-current' } }),
    ];

    const projection = runtimeArtifactProjection({ activeStageType: 'detail', brief, cast, detail, events, spine: '', volumes: '' });

    expect(projection.characterGraph?.nodes).toHaveLength(1);
    expect(projection.characterGraph?.updated_by).toBe('character-bible-artifact');
    expect(projection.worldbuilding?.rules).toEqual(['广播只会覆盖被明确标记的记忆']);
    expect(projection.stage).toEqual({
      character: '1 个 POV 引用人物圣经',
      worldbuilding: '2 个场景按需读取证据',
      foreshadow: '1 条章节交接进入 Context Manifest',
    });
    expect(projection.writeback).toEqual({ status: 'queued', label: '写回已进入事务队列', transactionId: 'tx-current' });
  });

  it('does not project retired Detail fields or unrelated stage writebacks', () => {
    const projection = runtimeArtifactProjection({
      activeStageType: 'detail',
      brief,
      cast,
      detail: JSON.stringify({ schema_version: 3, chapters: [], character_shift: [] }),
      events: [runEvent('writeback.failed', { run_id: 'run-1', stage_id: 'text', sequence: 2, payload: { transaction_id: 'tx-text' } })],
      spine: '',
      volumes: '',
    });

    expect(projection.stage).toEqual({});
    expect(projection.writeback.status).toBe('not_proposed');
    expect(projection.writeback.transactionId).toBe('');
  });
});
