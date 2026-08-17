// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GraphRunEnvelope, RunHistoryItem } from '../contracts';
import type { HydratedRunState } from './runState';
import { useRunHistoryActions } from './useRunHistoryActions';

const runId = 'run-branch-current';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('useRunHistoryActions', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('rehydrates upstream committed artifacts when history opens the current branch run', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === `/api/runs/${runId}`) return jsonResponse(runEnvelope());
      if (url.endsWith('/brief-committed-1')) {
        return jsonResponse(artifactRecord('brief', 'brief-committed-1', { title: '潮汐证词' }));
      }
      if (url.endsWith('/spine-committed-1')) {
        return jsonResponse(artifactRecord('spine', 'spine-committed-1', { turns: [{ id: 'turn-1' }] }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);
    const onRestore = vi.fn(async (_hydrated: HydratedRunState, _reconnect: boolean) => undefined);
    const onWarning = vi.fn();
    const stopActiveStream = vi.fn();
    let actions: ReturnType<typeof useRunHistoryActions> | null = null;

    function Harness() {
      actions = useRunHistoryActions({
        activeRunId: runId,
        cancelInitialRecovery: vi.fn(),
        historyRefresh: vi.fn(async () => undefined),
        onProjectContext: vi.fn(async () => undefined),
        onRestore,
        onWarning,
        runControlState: 'paused',
        running: false,
        setRunSource: vi.fn(),
        stopActiveStream,
      });
      return null;
    }

    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<Harness />));
    let stageId = '';
    await act(async () => {
      stageId = await actions!.openRun(historyItem());
    });
    act(() => root.unmount());

    expect(stageId).toBe('volumes');
    expect(stopActiveStream).toHaveBeenCalledOnce();
    expect(onRestore).toHaveBeenCalledOnce();
    expect(onRestore.mock.calls[0][0].events).toEqual(expect.arrayContaining([
      expect.objectContaining({ stage_id: 'brief', type: 'artifact.committed' }),
      expect.objectContaining({ stage_id: 'spine', type: 'artifact.committed' }),
    ]));
  });

});

function runEnvelope(): GraphRunEnvelope {
  return {
    definition: {
      architecture_version: 'phase27-vnext',
      run_id: runId,
      project_id: 'project-1',
    },
    read_model: {
      run_id: runId,
      project_id: 'project-1',
      thread_id: runId,
      status: 'awaiting_decision',
      active_stage_id: 'volumes',
      artifact_refs: {
        brief: 'brief-committed-1',
        spine: 'spine-committed-1',
      },
      pending_decisions: [{ node_id: 'volumes.human_decision' }],
      checkpoint_id: 'checkpoint-volumes',
    },
  } as unknown as GraphRunEnvelope;
}

function artifactRecord(stageId: 'brief' | 'spine', artifactId: string, payload: Record<string, unknown>) {
  return {
    artifact_id: artifactId,
    run_id: runId,
    stage_id: stageId,
    status: 'committed',
    payload,
    signature: 'a'.repeat(64),
    created_at: stageId === 'brief' ? '2026-08-14T00:00:01Z' : '2026-08-14T00:00:02Z',
    source: 'decision:test',
  };
}

function historyItem(): RunHistoryItem {
  return {
    run_id: runId,
    project_id: 'project-1',
    title: '潮汐证词',
    quality_mode: 'deep',
    status: 'awaiting_decision',
    current_stage: { id: 'volumes', label: '分卷架构', type: 'volumes' },
    completed_stage_ids: ['brief', 'spine', 'cast'],
    created_at: '2026-08-14T00:00:00Z',
    updated_at: '2026-08-14T00:00:00Z',
    completed_at: '',
    words: 0,
    total_tokens: 0,
    estimated_cost_usd: null,
    summary: '',
    can_branch: true,
    checkpoint_id: 'checkpoint-volumes',
    export_ready: false,
    export_count: 0,
    latest_export: null,
  };
}

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
