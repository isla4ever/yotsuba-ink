import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { parallelDeliverySnapshot } from './parallelDeliveryModel';
import type { WritingArtifact } from './writingArtifactModel';

const writing = {
  schema_version: 1,
  status: 'running',
  target_chapters: 2,
  context_packet: {},
  context_packets: [],
  chapter_deltas: [],
  chapters: [
    { id: 'chapter-1', title: '第一章', content: '正文', words: 2, status: 'completed', summary_dirty: false, quality_recheck: { status: 'passed' } },
  ],
  quality_reports: [],
  wiki_writebacks: [],
  chapter_summaries: [],
} as unknown as WritingArtifact;

describe('parallelDeliverySnapshot', () => {
  it('keeps preview available while final delivery gates remain explicit', () => {
    const events: RunEvent[] = [{
      type: 'parallel_delivery_ready',
      run_id: 'run-1',
      node_id: 'cover',
      node_type: 'cover_image',
      parallel_delivery: { status: 'ready', ready_count: 2, total: 3 },
    }];

    const snapshot = parallelDeliverySnapshot(events, writing);

    expect(snapshot.status).toBe('ready');
    expect(snapshot.coverReady).toBe(2);
    expect(snapshot.finalGates.find((gate) => gate.key === 'chapters')?.state).toBe('pending');
    expect(snapshot.finalGates.find((gate) => gate.key === 'canon')?.state).toBe('checking');
  });

  it('uses the latest lifecycle and requires a readable formal cover asset', () => {
    const staleCoverArtifact = {
      selected_candidate_id: 'cover-a',
      candidates: [{
        id: 'cover-a',
        image_url: '',
        composition: '中央构图',
        palette: '冷青',
        quality_summary: '',
        asset_status: 'ready',
        asset_source: 'production',
      }],
      asset_generation: { status: 'ready', ready_count: 1, total: 1 },
    };
    const baseEvents = [
      {
        type: 'parallel_delivery_started',
        run_id: 'run-1',
        node_id: 'cover',
        node_type: 'cover_image',
        parallel_delivery: { status: 'running', ready_count: 0, total: 1 },
      },
      {
        type: 'cover_asset_ready',
        run_id: 'run-1',
        node_id: 'cover',
        node_type: 'cover_image',
        artifact: staleCoverArtifact,
      },
      {
        type: 'parallel_delivery_ready',
        run_id: 'run-1',
        node_id: 'cover',
        node_type: 'cover_image',
        parallel_delivery: { status: 'ready', ready_count: 1, total: 1 },
      },
    ] as RunEvent[];

    const staleAsset = parallelDeliverySnapshot(baseEvents, writing);
    expect(staleAsset.status).toBe('ready');
    expect(staleAsset.coverReady).toBe(0);
    expect(staleAsset.finalGates.find((gate) => gate.key === 'cover')?.state).toBe('pending');

    const readableAsset = parallelDeliverySnapshot([
      ...baseEvents,
      {
        ...baseEvents[1],
        artifact: {
          ...staleCoverArtifact,
          candidates: [{
            ...staleCoverArtifact.candidates[0],
            image_url: '/api/runs/run-1/cover-assets/cover-a',
          }],
        },
      },
    ] as RunEvent[], writing);
    expect(readableAsset.coverReady).toBe(1);
    expect(readableAsset.finalGates.find((gate) => gate.key === 'cover')?.state).toBe('ready');
  });
});
