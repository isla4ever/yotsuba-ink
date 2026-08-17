// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { RunControlState, RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { useRunStreamController } from './useRunStreamController';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('useRunStreamController recovery replay', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resets the run cursor when a presentation restore requests a full replay', async () => {
    const event = runEvent('decision.required', {
      run_id: 'run-branch',
      stage_id: 'volumes',
      sequence: 44,
    });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => sseResponse([event]));
    vi.stubGlobal('fetch', fetchMock);
    let controller: ReturnType<typeof useRunStreamController> | null = null;

    function Harness() {
      controller = useRunStreamController(vi.fn());
      return null;
    }

    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<Harness />));
    await act(async () => {
      await controller!.consume(request());
      await controller!.consume(request());
      await controller!.consume({ ...request(), replayFromStart: true });
    });
    act(() => root.unmount());

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/runs/run-branch/events?after=0',
      '/api/runs/run-branch/events?after=44',
      '/api/runs/run-branch/events?after=0',
    ]);
  });

  it('reconnects a non-terminal EOF from the last delivered sequence exactly once', async () => {
    const progress = runEvent('node.completed', {
      run_id: 'run-branch',
      stage_id: 'spine',
      sequence: 44,
    });
    const terminal = runEvent('decision.required', {
      run_id: 'run-branch',
      stage_id: 'volumes',
      sequence: 45,
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(sseResponse([progress]))
      .mockResolvedValueOnce(sseResponse([progress, terminal]));
    vi.stubGlobal('fetch', fetchMock);
    const onEvent = vi.fn();
    let controller: ReturnType<typeof useRunStreamController> | null = null;

    function Harness() {
      controller = useRunStreamController(onEvent);
      return null;
    }

    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<Harness />));
    let result: RunControlState | null = null;
    await act(async () => {
      result = await controller!.consume(request());
    });
    act(() => root.unmount());

    expect(result).toBe('paused');
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/runs/run-branch/events?after=0',
      '/api/runs/run-branch/events?after=44',
    ]);
    expect(onEvent.mock.calls.map(([event]) => event.sequence)).toEqual([44, 45]);
  });

  it('retries a transient stream request failure without changing the cursor', async () => {
    const terminal = runEvent('decision.required', {
      run_id: 'run-branch',
      stage_id: 'volumes',
      sequence: 45,
    });
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('network disconnected'))
      .mockResolvedValueOnce(sseResponse([terminal]));
    vi.stubGlobal('fetch', fetchMock);
    const onEvent = vi.fn();
    let controller: ReturnType<typeof useRunStreamController> | null = null;

    function Harness() {
      controller = useRunStreamController(onEvent);
      return null;
    }

    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<Harness />));
    await act(async () => {
      await expect(controller!.consume(request())).resolves.toBe('paused');
    });
    act(() => root.unmount());

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/runs/run-branch/events?after=0',
      '/api/runs/run-branch/events?after=0',
    ]);
    expect(onEvent.mock.calls.map(([event]) => event.sequence)).toEqual([45]);
  });

  it('does not reconnect after the active stream session is invalidated', async () => {
    const progress = runEvent('node.completed', {
      run_id: 'run-branch',
      stage_id: 'spine',
      sequence: 44,
    });
    const fetchMock = vi.fn(async () => sseResponse([progress]));
    vi.stubGlobal('fetch', fetchMock);
    let controller: ReturnType<typeof useRunStreamController> | null = null;

    function Harness() {
      controller = useRunStreamController(() => controller!.invalidate());
      return null;
    }

    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<Harness />));
    await act(async () => {
      await expect(controller!.consume(request())).rejects.toMatchObject({ name: 'AbortError' });
    });
    act(() => root.unmount());

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

function request() {
  return {
    inputs: {} as RunInputs,
    kind: 'existing' as const,
    runId: 'run-branch',
    workflow: {} as WorkflowDefinition,
  };
}

function sseResponse(events: RunEvent[]) {
  const body = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}
