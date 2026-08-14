import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../../contracts';
import { defaultWorkflow } from '../../state/defaultWorkflow';
import { stickyArtifactsFromEvents } from '../../state/runReducer';
import { buildMonitorSnapshot } from './monitorModel';

let sequence = 0;

function event(partial: Partial<RunEvent>): RunEvent {
  sequence += 1;
  return {
    chapter_id: '',
    checkpoint_id: '',
    event_id: `event-${sequence}`,
    node_id: partial.stage_id ? `${partial.stage_id}.node` : 'graph.node',
    occurred_at: new Date(1700000000000 + sequence * 1000).toISOString(),
    payload: null,
    payload_ref: '',
    run_id: 'run-1',
    sequence,
    stage_id: null,
    status: '',
    thread_id: 'run-1',
    type: 'node.started',
    ...partial,
  } as RunEvent;
}

const detailPayload = {
  chapters: [
    {
      cast_ids: ['subject-1'],
      handoff: '深夜书房',
      pov: 'subject-1',
      purpose: '建立封闭环境',
      ref: 'chapter-1',
      scenes: [{ conflict: 'c', objective: 'o', place: 'p', result: 'r', turn: 't' }],
      volume_ref: 'volume-1',
    },
    {
      cast_ids: ['subject-1'],
      handoff: '黎明',
      pov: 'subject-1',
      purpose: '追查密道',
      ref: 'chapter-2',
      scenes: [{ conflict: 'c', objective: 'o', place: 'p', result: 'r', turn: 't' }],
      volume_ref: 'volume-1',
    },
  ],
};

const volumesPayload = {
  volumes: [{
    cast_ids: ['subject-1'],
    climax: '揭露',
    closure: '反转',
    conflict: '互相猜疑',
    id: 'volume-1',
    length_hint: 'medium',
    promise: '暴风雪山庄',
    thread_ids: [],
    turn_refs: ['turn-1'],
  }],
};

describe('buildMonitorSnapshot', () => {
  it('builds the volume→chapter tree with delivery-truthful statuses', () => {
    // Authored oldest-first, reversed to the app's newest-first ordering.
    const events = [
      event({ payload: volumesPayload, stage_id: 'volumes', type: 'artifact.committed' }),
      event({ payload: detailPayload, stage_id: 'detail', type: 'artifact.committed' }),
      event({
        chapter_id: 'chapter-1',
        payload: { author_status: 'accepted', chapter_id: 'chapter-1', content: '正文'.repeat(30), title: '第1章', version_id: 'v1' },
        stage_id: 'text',
        type: 'artifact.committed',
      }),
      event({ chapter_id: 'chapter-2', stage_id: 'text', type: 'node.started' }),
    ].reverse();

    const snapshot = buildMonitorSnapshot(events, defaultWorkflow);

    expect(snapshot.tree).toHaveLength(1);
    const [volume] = snapshot.tree;
    expect(volume.promise).toBe('暴风雪山庄');
    expect(volume.chapters.map((chapter) => chapter.status)).toEqual(['done', 'writing']);
    // Placeholder titles fall back to the blueprint purpose in the UI.
    expect(volume.chapters[0].title).toBe('');
    expect(volume.chapters[0].words).toBe(60);
    expect(snapshot.totals.chaptersDone).toBe(1);
    expect(snapshot.totals.chaptersTotal).toBe(2);
  });

  it('reports the newest touched stage as active and per-stage metrics', () => {
    const events = [
      event({ payload: detailPayload, stage_id: 'detail', type: 'artifact.committed' }),
      event({ chapter_id: 'chapter-1', stage_id: 'text', type: 'node.started' }),
    ];
    const snapshot = buildMonitorSnapshot(events.reverse(), defaultWorkflow);
    expect(snapshot.activeStageType).toBe('text');
    const detailEntry = snapshot.stages.find((stage) => stage.type === 'detail');
    expect(detailEntry?.metric).toBe('2 章施工图');
  });

  it('backfills evicted stage artifacts and statuses from the sticky record', () => {
    // A long run trimmed every early event out of the 500-cap window; only the
    // sticky record (built before eviction) still knows about them.
    const evicted = [
      event({ payload: volumesPayload, stage_id: 'volumes', type: 'artifact.committed' }),
      event({ payload: detailPayload, stage_id: 'detail', type: 'artifact.committed' }),
      event({
        chapter_id: 'chapter-1',
        payload: { author_status: 'accepted', chapter_id: 'chapter-1', content: '第一章定稿', title: '第1章', version_id: 'v1' },
        stage_id: 'text',
        type: 'artifact.committed',
      }),
    ];
    const sticky = stickyArtifactsFromEvents([...evicted].reverse());
    const windowEvents = [
      event({
        chapter_id: 'chapter-2',
        payload: { author_status: 'accepted', chapter_id: 'chapter-2', content: '第二章定稿', title: '第2章', version_id: 'v2' },
        stage_id: 'text',
        type: 'artifact.committed',
      }),
      event({ stage_id: 'export', type: 'run.completed' }),
    ].reverse();

    const snapshot = buildMonitorSnapshot(windowEvents, defaultWorkflow, sticky);

    expect(snapshot.volumes?.volumes[0]?.promise).toBe('暴风雪山庄');
    expect(snapshot.detail?.chapters).toHaveLength(2);
    expect(snapshot.tree).toHaveLength(1);
    expect(snapshot.tree[0].chapters.map((chapter) => chapter.status)).toEqual(['done', 'done']);
    expect(snapshot.totals.chaptersDone).toBe(2);
    const volumesEntry = snapshot.stages.find((stage) => stage.type === 'volumes');
    expect(volumesEntry?.status).toBe('done');
  });
});
