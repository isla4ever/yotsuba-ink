import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { captureRunResetSnapshot } from './runResetState';

const lengthEnvelope = {
  word_target_soft: 100_000,
  chapter_target_soft: 3,
};

describe('captureRunResetSnapshot', () => {
  it('captures the current run for a paused local-only restore', () => {
    const events: RunEvent[] = [
      runEvent('checkpoint.saved', { run_id: 'run-reset-safe', stage_id: 'detail', node_id: 'graph.checkpoint', checkpoint_id: 'cp-detail', occurred_at: '2026-07-19T12:00:01Z', sequence: 2 }),
      runEvent('run.started', { run_id: 'run-reset-safe', stage_id: 'brief', node_id: 'load_run', occurred_at: '2026-07-19T12:00:00Z', sequence: 1 }),
    ];

    const snapshot = captureRunResetSnapshot({
      automationCockpitReady: true,
      decision: {
        approvalDraft: '当前人工稿',
        approvalPending: true,
        approvalSource: '服务端来源稿',
        checkpointContinueReady: false,
        checkpointStageId: 'detail',
        briefContinueReady: false,
      },
      events,
      inputs: {
        project_id: 'project-reset-safe',
        title: '撤销恢复测试',
        theme: '旧港',
        quality_mode: 'balanced',
        length_envelope: lengthEnvelope,
        run_intent: {
          project_brief: { narrative_profile: '心理戏剧家' },
          knowledge_strategy: {},
        },
        export_preferences: { format: 'zip', author: '', version_note: '' },
      },
      runSource: 'backend',
      state: {
        activeRunId: 'run-reset-safe',
        paused: false,
        runControlState: 'running',
        selectedId: 'detail',
        stickyArtifacts: { chapters: {}, stages: {} },
      },
    });

    expect(snapshot).not.toBeNull();
    expect(snapshot?.runSource).toBe('backend');
    expect(snapshot?.hydrated).toMatchObject({
      activeRunId: 'run-reset-safe',
      approvalDraft: '当前人工稿',
      approvalPending: true,
      automationCockpitReady: true,
      checkpointStageId: 'detail',
      paused: true,
      runControlState: 'paused',
      selectedId: 'detail',
    });
    expect(snapshot?.hydrated.events).toEqual(events);
    expect(snapshot?.hydrated.inputs?.run_intent?.project_brief.narrative_profile).toBe('心理戏剧家');
  });

  it('does not offer undo without a persisted event context', () => {
    const snapshot = captureRunResetSnapshot({
      automationCockpitReady: false,
      decision: {
        approvalDraft: '',
        approvalPending: false,
        approvalSource: '',
        checkpointContinueReady: false,
        checkpointStageId: '',
        briefContinueReady: false,
      },
      events: [],
      runSource: 'backend',
      state: {
        activeRunId: 'starting-run',
        paused: false,
        runControlState: 'starting',
        selectedId: 'brief',
        stickyArtifacts: { chapters: {}, stages: {} },
      },
    });

    expect(snapshot).toBeNull();
  });
});
