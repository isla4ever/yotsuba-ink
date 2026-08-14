import { describe, expect, it } from 'vitest';
import type { GraphRunEnvelope, RunEvent } from '../contracts';
import {
  frozenCoverAssetBindingFixture,
  frozenProviderBindingsFixture,
} from '../contracts/runTestFixtures';
import { runEvent } from '../contracts/runEventTestFactory';
import { scaleProfileFromLengthEnvelope } from '../lib/narrativeScale';
import {
  hydrateGraphRun,
  hydrateLocalRunControl,
  resolveServerRunRecovery,
} from './runState';

const runId = 'run-recovery-test';
const lengthEnvelope = {
  word_target_soft: 100_000,
  chapter_target_soft: 3,
};

describe('LangGraph read-model recovery', () => {
  it('reconnects a running graph using the active stage from the read model', () => {
    const resolution = resolveServerRunRecovery(envelope({
      status: 'running',
      active_stage_id: 'spine',
      stage_status: stageStatus({ brief: 'completed', spine: 'running' }),
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(true);
    expect(resolution.hydrated.selectedId).toBe('spine');
    expect(resolution.hydrated.runControlState).toBe('running');
    expect(resolution.hydrated.events).toEqual([]);
  });

  it('restores an active interrupt without inventing a continuation state', () => {
    const resolution = resolveServerRunRecovery(envelope({
      status: 'awaiting_decision',
      active_stage_id: 'spine',
      checkpoint_id: 'checkpoint-spine',
      pending_decisions: [{
        type: 'stage_artifact_decision',
        decision_id: 'run-recovery-test:spine:artifact-1',
        node_id: 'spine.human_decision',
        domain_revision: 2,
      }],
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(true);
    expect(resolution.hydrated.approvalPending).toBe(true);
    expect(resolution.hydrated.checkpointStageId).toBe('spine');
    expect(resolution.hydrated.checkpointContinueReady).toBe(false);
    expect(resolution.hydrated.paused).toBe(true);
  });

  it('treats completed, failed, cancelled, and mismatched graphs as non-restorable', () => {
    expect(resolveServerRunRecovery(envelope({ status: 'completed' }), runId))
      .toEqual({ kind: 'discard', reason: 'completed' });
    expect(resolveServerRunRecovery(envelope({ status: 'failed' }), runId))
      .toEqual({ kind: 'discard', reason: 'failed' });
    expect(resolveServerRunRecovery(envelope({ status: 'cancelled' }), runId))
      .toEqual({ kind: 'discard', reason: 'failed' });
    expect(resolveServerRunRecovery(envelope({ run_id: 'another-run' }), runId))
      .toEqual({ kind: 'discard', reason: 'invalid' });
  });

  it('derives local reset state only from explicit vNext events', () => {
    const events: RunEvent[] = [
      runEvent('artifact.candidate_ready', { run_id: runId, stage_id: 'brief', payload: { title: '雾港回声' }, sequence: 2 }),
      runEvent('decision.required', { run_id: runId, stage_id: 'brief', node_id: 'brief.human_decision', payload: { decision_id: 'decision-1' }, sequence: 3 }),
    ];
    const hydrated = hydrateLocalRunControl({
      activeRunId: runId,
      events,
      paused: true,
      runControlState: 'paused',
      selectedId: 'brief',
    });

    expect(hydrated.approvalPending).toBe(true);
    expect(hydrated.approvalDraft).toContain('雾港回声');
    expect(hydrated.checkpointStageId).toBe('brief');
  });

  it('projects a Graph envelope without using local event history', () => {
    expect(hydrateGraphRun(envelope({ status: 'created' })).events).toEqual([]);
  });
});

function envelope(readModel: Partial<GraphRunEnvelope['read_model']> = {}): GraphRunEnvelope {
  return {
    definition: {
      architecture_version: 'phase27-vnext',
      run_id: runId,
      project_id: 'project-1',
      workflow_id: 'workflow-phase27',
      workflow_revision: 'phase27-vnext',
      workflow_digest: 'a'.repeat(64),
      quality_mode: 'balanced',
      inputs: {},
      scale_profile: scaleProfileFromLengthEnvelope(lengthEnvelope),
      provider_bindings: frozenProviderBindingsFixture(),
      cover_asset_binding: frozenCoverAssetBindingFixture(),
      export_preferences: { format: 'zip', author: '', version_note: '' },
      branch_origin: null,
      created_at: '2026-08-10T00:00:00Z',
    },
    read_model: {
      run_id: runId,
      project_id: 'project-1',
      thread_id: runId,
      status: 'created',
      active_stage_id: 'brief',
      active_chapter_number: 0,
      context_manifest_ref: '',
      stage_status: {
        brief: 'available',
        spine: 'locked',
        cast: 'locked',
        volumes: 'locked',
        detail: 'locked',
        text: 'locked',
        cover: 'locked',
        export: 'locked',
      },
      artifact_refs: {},
      pending_decisions: [],
      provider_usage: {
        provider_operations: 0,
        succeeded_operations: 0,
        failed_operations: 0,
        pending_operations: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        reasoning_tokens: 0,
      },
      failure: null,
      checkpoint_id: '',
      updated_at: '2026-08-10T00:00:00Z',
      ...readModel,
    },
  };
}

function stageStatus(
  overrides: Partial<GraphRunEnvelope['read_model']['stage_status']> = {},
): GraphRunEnvelope['read_model']['stage_status'] {
  return {
    brief: 'available',
    spine: 'locked',
    cast: 'locked',
    volumes: 'locked',
    detail: 'locked',
    text: 'locked',
    cover: 'locked',
    export: 'locked',
    ...overrides,
  };
}
