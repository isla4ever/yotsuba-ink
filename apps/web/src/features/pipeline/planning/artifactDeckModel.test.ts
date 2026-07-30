import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import type { RunEvent } from '../contracts';
import { buildArtifactDeckItems, buildPlanningStagePosition } from './artifactDeckModel';

describe('buildArtifactDeckItems', () => {
  it('maps the seven real stages to artifacts, decisions, writebacks and next-stage needs', () => {
    const items = buildArtifactDeckItems(defaultWorkflow, [], 'detail');
    expect(items).toHaveLength(7);
    expect(items[0]).toMatchObject({
      artifact: '方向 · 世界观 · 人物档案',
      decision: '确认创作方向',
      writeback: '世界观 · 人物关系网',
    });
    expect(items[3]).toMatchObject({
      nextDependency: '章节蓝图 · 连续性上下文',
      nextStage: defaultWorkflow.nodes[4].label,
      status: 'current',
      writeback: '人物关系网 · 世界观 · Wiki',
    });
    expect(items[6]).toMatchObject({ nextDependency: '已校验交付包', nextStage: '流程结束' });
  });

  it('derives confirmed, running and attention states from real lifecycle events', () => {
    const events = [
      { type: 'node_failed', run_id: 'run-1', node_id: 'detail' },
      { type: 'node_started', run_id: 'run-1', node_id: 'summary' },
      { type: 'node_completed', run_id: 'run-1', node_id: 'info' },
    ] as RunEvent[];
    const items = buildArtifactDeckItems(defaultWorkflow, events, 'detail');
    expect(items.find((item) => item.id === 'info')?.status).toBe('confirmed');
    expect(items.find((item) => item.id === 'summary')?.status).toBe('running');
    expect(items.find((item) => item.id === 'detail')?.status).toBe('attention');
  });

  it('shows incomplete Cover and Export deliveries as 待完善 instead of confirmed', () => {
    const events = [
      { type: 'node_completed', run_id: 'run-1', node_id: 'export', result: { manifest: [{}], package_status: { ready: true } } },
      { type: 'node_completed', run_id: 'run-1', node_id: 'cover', result: {
        brief: '封面简报',
        prompt: 'cover prompt',
        candidates: [{ id: 'cover-1', image_url: '' }],
        selected_candidate_id: 'cover-1',
      } },
    ] as RunEvent[];
    const items = buildArtifactDeckItems(defaultWorkflow, events, 'cover');
    expect(items.find((item) => item.id === 'cover')).toMatchObject({ status: 'attention', statusLabel: '待完善' });
    expect(items.find((item) => item.id === 'export')).toMatchObject({ status: 'attention', statusLabel: '待完善' });
    expect(buildPlanningStagePosition(defaultWorkflow, events, 'export')).toMatchObject({ completed: 0, current: 7, total: 7 });
  });
});
