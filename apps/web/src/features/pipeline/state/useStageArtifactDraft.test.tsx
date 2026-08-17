// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import {
  STAGE_DRAFT_AUTOSAVE_MS,
  useStageArtifactDraft,
} from './useStageArtifactDraft';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('useStageArtifactDraft', () => {
  it('restores the current decision draft and autosaves later edits', async () => {
    vi.useFakeTimers();
    const sourceArtifact = {
      volumes: [{ title: '盐晶初响', promise: '发现证据', conflict: '证据受潮', climax: '保全晶片', closure: '进入调查', turn_refs: ['turn-1'], cast_ids: ['subject-1'], length_hint: 'medium' }],
    };
    const restoredArtifact = {
      volumes: [{ ...sourceArtifact.volumes[0], conflict: '听证前证据链受到质疑' }],
    };
    const decisionId = 'run-1:volumes:volumes-candidate-1';
    const decision = runEvent('decision.required', {
      stage_id: 'volumes',
      node_id: 'volumes.human_decision',
      payload: {
        decision_id: decisionId,
        artifact_ref: 'volumes-candidate-1',
        domain_revision: 3,
      },
    });
    const record = {
      draft_id: 'volumes-draft-1',
      run_id: 'run-1',
      stage_id: 'volumes',
      decision_id: decisionId,
      domain_revision: 3,
      source_artifact_id: 'volumes-candidate-1',
      payload: restoredArtifact,
      signature: 'a'.repeat(64),
      created_at: '2026-08-15T00:00:00Z',
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(record))
      .mockResolvedValueOnce(jsonResponse({ ...record, draft_id: 'volumes-draft-2' }));
    vi.stubGlobal('fetch', fetchMock);
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    let observed: ReturnType<typeof useStageArtifactDraft> | undefined;
    // Candidate events are compact JSON while edited forms emit pretty JSON.
    // Identity is the immutable candidate source, not serialized formatting.
    const source = JSON.stringify(sourceArtifact);

    function Harness({ events }: { events: RunEvent[] }) {
      observed = useStageArtifactDraft({ events, runId: 'run-1', source, stageId: 'volumes' });
      return null;
    }

    await act(async () => {
      root.render(<Harness events={[decision]} />);
      await Promise.resolve();
    });
    expect(observed?.status).toBe('saved');
    expect(JSON.parse(observed?.draft?.value ?? '{}')).toEqual(restoredArtifact);

    const edited = { volumes: [{ ...restoredArtifact.volumes[0], conflict: '听证逐项质证，证据完整性受到挑战' }] };
    act(() => observed?.change('volumes', source, JSON.stringify(edited, null, 2)));
    expect(observed?.status).toBe('dirty');

    await act(async () => {
      vi.advanceTimersByTime(STAGE_DRAFT_AUTOSAVE_MS);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(observed?.status).toBe('saved');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `/api/runs/run-1/stage-drafts/${encodeURIComponent(decisionId)}`,
    );
    expect(JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      domain_revision: 3,
      source_artifact_id: 'volumes-candidate-1',
      artifact: edited,
    });

    act(() => root.unmount());
    container.remove();
  });
});

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
