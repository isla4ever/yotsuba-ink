import { describe, expect, it } from 'vitest';
import type { RunEvent, WorkflowStage } from '../contracts';
import { buildRunEventIndex } from './runEventIndex';
import { completedDeliveryStageIds, stageDeliveryStatus } from './stageDeliveryStatus';

const coverStage = { id: 'cover', type: 'cover_image' } as const;
const exportStage = { id: 'export', type: 'export_artifact' } as const;
const ordinaryStage = { id: 'summary', type: 'summary' } as const;

describe('stageDeliveryStatus', () => {
  it('keeps a lifecycle-complete Cover in attention until its selected image asset is ready', () => {
    const index = buildRunEventIndex([
      event('node_completed', 'cover', { result: coverResult('') }),
    ]);
    expect(stageDeliveryStatus(index, coverStage)).toBe('attention');
  });

  it('marks Cover done only when the selected ready candidate has a valid image source', () => {
    const index = buildRunEventIndex([
      event('node_completed', 'cover', { result: coverResult('/api/runs/run-1/cover-assets/cover-1') }),
    ]);
    expect(stageDeliveryStatus(index, coverStage)).toBe('done');
  });

  it('keeps legacy Export in attention when cover or canon delivery gates are missing', () => {
    const index = buildRunEventIndex([
      event('node_completed', 'export', { result: exportResult(false) }),
    ]);
    expect(stageDeliveryStatus(index, exportStage)).toBe('attention');
  });

  it('accepts a structured run_export_ready artifact only when all delivery gates pass', () => {
    const artifact = exportResult(true);
    const index = buildRunEventIndex([
      event('run_export_ready', 'export', { artifact }),
      event('node_completed', 'export', { result: artifact }),
    ]);
    expect(stageDeliveryStatus(index, exportStage)).toBe('done');
  });

  it('preserves ordinary lifecycle behavior and excludes attention stages from Header progress', () => {
    const stages: Array<Pick<WorkflowStage, 'id' | 'type'>> = [ordinaryStage, coverStage, exportStage];
    const index = buildRunEventIndex([
      event('node_completed', 'export', { result: exportResult(true) }),
      event('node_completed', 'cover', { result: coverResult('') }),
      event('node_completed', 'summary'),
    ]);
    expect(stageDeliveryStatus(index, ordinaryStage)).toBe('done');
    expect(completedDeliveryStageIds(index, stages)).toEqual(['summary', 'export']);
  });
});

function event(type: string, nodeId: string, extra: Partial<RunEvent> = {}): RunEvent {
  return { type, run_id: 'run-1', node_id: nodeId, ...extra };
}

function coverResult(imageUrl: string) {
  return {
    brief: '雾港悬疑封面',
    composition: '旧磁带位于画面中央',
    prompt: 'cinematic mystery cover',
    candidates: [{
      id: 'cover-1',
      image_url: imageUrl,
      asset_status: imageUrl ? 'ready' : 'planned',
    }],
    selected_candidate_id: 'cover-1',
  };
}

function exportResult(ready: boolean) {
  return {
    manifest: [{ name: 'novel.zip', format: 'zip', status: 'ready' }],
    chapters: [{ id: 'chapter-1', title: '第一章', status: 'completed' }],
    cover_asset: ready ? { asset_id: 'cover-1', image_url: '/api/assets/cover-1' } : null,
    validation: {
      chapters: 'ready',
      cover: ready ? 'ready' : 'pending',
      quality: 'ready',
      ...(ready ? { canon: 'ready' } : {}),
    },
    package_status: { kind: 'zip', name: 'novel.zip', ready: true },
  };
}
