import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../../state/defaultWorkflow';
import type { RunEvent } from '../../contracts';
import { runEvent } from '../../contracts/runEventTestFactory';
import { bibleCanonRows, bibleCharacterGraph, bibleForeshadowRows, bibleWorldView } from './storyBibleModel';

const event = (stageId: string, artifact: Record<string, unknown>): RunEvent => runEvent('artifact.committed', {
  payload: artifact,
  run_id: 'run-1',
  stage_id: stageId as RunEvent['stage_id'],
});

describe('Phase 27 Story Bible projection', () => {
  it('reads the frozen Character Bible without enriching it from later stages', () => {
    const cast = {
      subjects: [{ id: 'subject-lin', name: '林默', kind: 'protagonist', function: '调查者', drive: '找到母带', change: '承认恐惧', debut: 'chapter:1', limits: [], demand_refs: ['demand-investigator'] }],
      relations: [],
    };

    const result = bibleCharacterGraph([event('cast', cast)], defaultWorkflow);

    expect(result.source).toBe('committed');
    expect(result.graph.nodes.map((item) => item.id)).toEqual(['subject-lin']);
    expect(result.graph.updated_by).toBe('character-bible-artifact');
  });

  it('projects world rules from the frozen Brief without Detail-derived anchors', () => {
    const brief = {
      title: '雾港',
      premise: '追查母带',
      promise: '真相会被查明',
      world_rules: ['广播覆盖记忆'],
      theme: '真相的代价？',
      ending_promise: '公开真相',
      voice: '第三人称有限视角',
      length_envelope: { word_target_soft: 80000, chapter_target_soft: 24 },
    };

    const world = bibleWorldView([event('brief', brief)]);

    expect(world.rules[0].text).toBe('广播覆盖记忆');
    expect(world.anchors).toEqual([]);
  });

  it('projects foreshadow only from Evidence and Canon only from committed writeback', () => {
    const evidence = runEvent('evidence.proposed', {
      run_id: 'run-1',
      stage_id: 'text',
      chapter_id: 'chapter-1',
      event_id: 'evidence-1',
      payload: { kind: 'foreshadow', subject_ref: 'thread-watch', claim: '怀表在柜台出现' },
    });
    const writeback = runEvent('writeback.committed', { run_id: 'run-1', stage_id: 'text', chapter_id: 'chapter-1', event_id: 'wb-1', payload: { transaction_id: 'canon-chapter-1' } });

    expect(bibleForeshadowRows([evidence])[0]).toMatchObject({ name: 'thread-watch', status: '推进' });
    expect(bibleCanonRows([writeback])[0]).toMatchObject({ status: 'active', target: 'canon-chapter-1' });
  });
});
