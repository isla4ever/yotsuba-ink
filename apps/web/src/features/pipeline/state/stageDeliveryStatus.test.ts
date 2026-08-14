import { describe, expect, it } from 'vitest';
import type { RunEvent, WorkflowStage } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { buildRunEventIndex } from './runEventIndex';
import { completedDeliveryStageIds, stageDeliveryStatus } from './stageDeliveryStatus';

const coverStage = { id: 'cover', type: 'cover' } as const;
const exportStage = { id: 'export', type: 'export' } as const;
const ordinaryStage = { id: 'spine', type: 'spine' } as const;

describe('stageDeliveryStatus', () => {
  it('keeps a committed Cover in attention until an asset is selected', () => {
    const index = buildRunEventIndex([
      event('artifact.committed', 'cover', { payload: coverResult('') }),
    ]);
    expect(stageDeliveryStatus(index, coverStage)).toBe('attention');
  });

  it('marks Cover done when the vNext artifact selects an asset', () => {
    const index = buildRunEventIndex([
      event('artifact.committed', 'cover', { payload: coverResult('asset-cover-1') }),
    ]);
    expect(stageDeliveryStatus(index, coverStage)).toBe('done');
  });

  it('keeps Export in attention when no chapter version is selected', () => {
    const index = buildRunEventIndex([
      event('artifact.committed', 'export', { payload: exportResult(false) }),
    ]);
    expect(stageDeliveryStatus(index, exportStage)).toBe('attention');
  });

  it('accepts the committed vNext Export artifact when chapter versions are selected', () => {
    const artifact = exportResult(true);
    const index = buildRunEventIndex([
      event('artifact.committed', 'export', { payload: artifact }),
    ]);
    expect(stageDeliveryStatus(index, exportStage)).toBe('done');
  });

  it('preserves ordinary lifecycle behavior and excludes attention stages from Header progress', () => {
    const stages: Array<Pick<WorkflowStage, 'id' | 'type'>> = [ordinaryStage, coverStage, exportStage];
    const index = buildRunEventIndex([
      event('artifact.committed', 'export', { payload: exportResult(true) }),
      event('artifact.committed', 'cover', { payload: coverResult('') }),
      event('artifact.committed', 'spine', { payload: {} }),
    ]);
    expect(stageDeliveryStatus(index, ordinaryStage)).toBe('done');
    expect(completedDeliveryStageIds(index, stages)).toEqual(['spine', 'export']);
  });
});

function event(type: string, nodeId: string, extra: Partial<RunEvent> = {}): RunEvent {
  return runEvent(type, { run_id: 'run-1', stage_id: nodeId as RunEvent['stage_id'], node_id: `${nodeId}.commit_artifact`, ...extra });
}

function coverResult(selectedAssetId: string) {
  return {
    brief: {
      concept: '雾港悬疑封面',
      image_prompt: '浓雾中的旧广播塔与人物剪影',
      palette: ['#15191f', '#d9d2c3'],
      negative_constraints: ['不渲染文字'],
    },
    selected_asset_id: selectedAssetId,
  };
}

function exportResult(ready: boolean) {
  return {
    format: 'zip',
    chapter_version_ids: ready ? ['chapter-1-accepted'] : [],
    cover_asset_id: ready ? 'asset-cover-1' : '',
    metadata: { title: '雾港', author: '', version_note: '' },
    volumes: [{ title: '雾港残响', chapter_count: ready ? 1 : 1 }],
  };
}
