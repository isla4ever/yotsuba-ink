import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { buildArtifactDeckItems, buildPlanningStagePosition } from './artifactDeckModel';

describe('buildArtifactDeckItems', () => {
  it('maps the eight production stages to artifacts, decisions, writebacks and next-stage needs', () => {
    const items = buildArtifactDeckItems(defaultWorkflow, [], 'detail');
    expect(items).toHaveLength(8);
    expect(items[0]).toMatchObject({
      artifact: '前提 · 世界规则 · 叙事声音',
      decision: '冻结创作契约',
      writeback: 'Story Brief Artifact',
    });
    expect(items[4]).toMatchObject({
      nextDependency: '冻结的章节执行计划',
      nextStage: defaultWorkflow.nodes[5].label,
      status: 'current',
      writeback: 'Detail Artifact',
    });
    expect(items[7]).toMatchObject({ nextDependency: '流程完成', nextStage: '流程结束' });
  });

  it('derives confirmed, running and attention states from real lifecycle events', () => {
    const events = [
      runEvent('node.failed', { run_id: 'run-1', stage_id: 'detail', node_id: 'detail.generate_candidate' }),
      runEvent('node.started', { run_id: 'run-1', stage_id: 'summary', node_id: 'summary.generate_candidate' }),
      runEvent('artifact.committed', { run_id: 'run-1', stage_id: 'info', node_id: 'info.commit_artifact', payload: {} }),
    ];
    const items = buildArtifactDeckItems(defaultWorkflow, events, 'detail');
    expect(items.find((item) => item.id === 'info')?.status).toBe('confirmed');
    expect(items.find((item) => item.id === 'summary')?.status).toBe('running');
    expect(items.find((item) => item.id === 'detail')?.status).toBe('attention');
  });

  it('shows incomplete Cover and Export deliveries as 待完善 instead of confirmed', () => {
    const events = [
      runEvent('artifact.committed', { run_id: 'run-1', stage_id: 'export', node_id: 'export.commit_artifact', payload: {
        format: 'zip', chapter_version_ids: [], cover_asset_id: '', metadata: { title: '雾港', author: '', version_note: '' },
      } }),
      runEvent('artifact.committed', { run_id: 'run-1', stage_id: 'cover', node_id: 'cover.commit_artifact', payload: {
        brief: {
          concept: '封面简报', image_prompt: '雾港剪影', palette: ['#111827'], negative_constraints: [],
        },
        selected_asset_id: '',
      } }),
    ];
    const items = buildArtifactDeckItems(defaultWorkflow, events, 'cover');
    expect(items.find((item) => item.id === 'cover')).toMatchObject({ status: 'attention', statusLabel: '待完善' });
    expect(items.find((item) => item.id === 'export')).toMatchObject({ status: 'attention', statusLabel: '待完善' });
    expect(buildPlanningStagePosition(defaultWorkflow, events, 'export')).toMatchObject({ completed: 0, current: 8, total: 8 });
  });

  it('keeps awaiting decisions separate from generation and delivery attention', () => {
    const events = [
      runEvent('decision.required', { run_id: 'run-1', stage_id: 'characters', node_id: 'characters.human_decision' }),
    ];
    expect(buildArtifactDeckItems(defaultWorkflow, events, 'characters').find((item) => item.id === 'characters'))
      .toMatchObject({ status: 'awaiting', statusLabel: '待决策' });
  });
});
