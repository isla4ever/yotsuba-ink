// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { GraphRunEnvelope } from '../contracts';
import {
  frozenCoverAssetBindingFixture,
  frozenProviderBindingsFixture,
} from '../contracts/runTestFixtures';
import { scaleProfileFromLengthEnvelope } from '../lib/narrativeScale';
import { useRunRecovery } from './useRunRecovery';
import type { StoredRunControlState } from './storage';

const runId = 'run-boot-recovery';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

function Harness({ present }: { present: boolean }) {
  useRunRecovery({
    loadRun: async () => completedEnvelope(),
    onDiscard: handlers.onDiscard,
    onRestore: handlers.onRestore,
    onSettled: handlers.onSettled,
    onWarning: vi.fn(),
    presentTerminalRuns: present,
    stored: stored(),
  });
  return null;
}

const handlers = {
  onDiscard: vi.fn(),
  onRestore: vi.fn(),
  onSettled: vi.fn(),
};

async function bootRecovery(present: boolean) {
  handlers.onDiscard = vi.fn();
  handlers.onRestore = vi.fn();
  let settle = () => {};
  const settled = new Promise<void>((resolve) => { settle = resolve; });
  handlers.onSettled = vi.fn(() => settle());
  const container = document.createElement('div');
  const root = createRoot(container);
  await act(async () => {
    root.render(<Harness present={present} />);
  });
  await act(async () => { await settled; });
  act(() => root.unmount());
  return handlers;
}

describe('useRunRecovery boot resolution', () => {
  it('drops a finished run on a normal boot', async () => {
    const result = await bootRecovery(false);
    expect(result.onDiscard).toHaveBeenCalledWith('completed');
    expect(result.onRestore).not.toHaveBeenCalled();
  });

  it('presents a finished run when the console itself is the boot route', async () => {
    const result = await bootRecovery(true);
    expect(result.onDiscard).not.toHaveBeenCalled();
    expect(result.onRestore).toHaveBeenCalled();
    expect(result.onRestore.mock.calls[0][0].activeRunId).toBe(runId);
  });
});

function stored(): StoredRunControlState {
  return {
    activeRunId: runId,
    events: [],
    paused: false,
    runControlState: 'running',
    selectedId: 'brief',
    stickyStageEvents: [],
    workspacePhase: 'running',
  };
}

function completedEnvelope(): GraphRunEnvelope {
  return {
    definition: {
      architecture_version: 'phase27-vnext',
      run_id: runId,
      project_id: 'project-1',
      workflow_id: 'workflow-phase27',
      workflow_revision: 'phase27-vnext',
      workflow_digest: 'a'.repeat(64),
      quality_mode: 'fast',
      inputs: {},
      scale_profile: scaleProfileFromLengthEnvelope({ word_target_soft: 100_000, chapter_target_soft: 3 }),
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
      status: 'completed',
      active_stage_id: 'export',
      active_chapter_number: 0,
      context_manifest_ref: '',
      stage_status: {
        brief: 'completed',
        spine: 'completed',
        cast: 'completed',
        volumes: 'completed',
        detail: 'completed',
        text: 'completed',
        cover: 'completed',
        export: 'completed',
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
    },
  };
}
