// @vitest-environment happy-dom

import { act, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
import type { HydratedRunState } from './runState';
import { useRunCommands } from './useRunCommands';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('useRunCommands recovery lifecycle', () => {
  it('hydrates immediately without waiting for the live stream to terminate', async () => {
    const neverEndingStream = new Promise<never>(() => undefined);
    const consume = vi.fn(() => neverEndingStream);
    const dispatchRun = vi.fn();
    const restoreDecision = vi.fn();
    let commands: ReturnType<typeof useRunCommands> | null = null;

    function Harness() {
      const eventsRef = useRef<RunEvent[]>([]);
      commands = useRunCommands({
        dispatchRun,
        eventsRef,
        history: { refresh: vi.fn() } as never,
        onSettingsRequired: vi.fn(),
        onWarning: vi.fn(),
        project: { id: 'project-1', title: '待定书名' },
        runInputs: runInputs(),
        setRunSource: vi.fn(),
        stageDecision: { restore: restoreDecision } as never,
        state: {
          activeRunId: 'old-run',
          paused: true,
          runControlState: 'paused',
          running: false,
          selectedId: 'detail',
          workspacePhase: 'running',
        },
        stream: { consume, invalidate: vi.fn() } as never,
        transitions: { reset: vi.fn() } as never,
        workflow: workflow(),
      });
      return null;
    }

    const root = createRoot(document.createElement('div'));
    act(() => root.render(<Harness />));
    await act(async () => {
      await commands!.restoreRecoveredRun(hydrated(), true);
    });
    act(() => root.unmount());

    expect(dispatchRun).toHaveBeenCalledWith(expect.objectContaining({
      type: 'run_restored',
      hydrated: expect.objectContaining({ activeRunId: 'new-run' }),
    }));
    expect(restoreDecision).toHaveBeenCalledOnce();
    expect(consume).toHaveBeenCalledOnce();
  });
});

function hydrated(): HydratedRunState {
  return {
    activeRunId: 'new-run',
    inputs: runInputs(),
    approvalPending: false,
    checkpointContinueReady: false,
    checkpointStageId: '',
    events: [],
    briefContinueReady: false,
    paused: false,
    runControlState: 'idle',
    selectedId: 'brief',
  };
}

function runInputs(): RunInputs {
  return {
    project_id: 'project-1',
    quality_mode: 'balanced',
    length_envelope: { word_target_soft: 100_000 },
    scale_overrides: { turn_target: null },
    run_intent: {
      project_brief: {
        genre: '科幻', audience: '', narrative_profile: '悬念导演', core_concept: '潮汐记忆公证', keywords: [], taboos: '',
      },
      knowledge_strategy: {
        reference_mode: 'smart_search', reference_keywords: [], reference_query_intent: '', reference_urls: [], knowledge_base_doc_ids: [], enable_web_search: false, reference_summary: '',
      },
    },
    export_preferences: { format: 'zip', author: '', version_note: '' },
  };
}

function workflow(): WorkflowDefinition {
  return {
    id: 'workflow-1',
    name: '平衡流水线',
    version: '29.12.0-natural-volume-boundaries',
    quality_mode: 'balanced',
    nodes: [{ id: 'brief', type: 'brief' }],
  } as WorkflowDefinition;
}
