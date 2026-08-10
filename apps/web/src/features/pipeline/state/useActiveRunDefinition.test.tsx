// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphRunDefinition } from '../contracts';
import { buildBookScalePlan } from '../lib/bookScalePlan';
import { useActiveRunDefinition } from './useActiveRunDefinition';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

function Harness({ expose, runId }: { expose: (value: ReturnType<typeof useActiveRunDefinition>) => void; runId: string }) {
  expose(useActiveRunDefinition(runId));
  return null;
}

describe('useActiveRunDefinition', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  it('keeps the definition unavailable while loading and exposes only the frozen result', async () => {
    let resolveResponse: (value: Response) => void = () => undefined;
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    })));
    let observed: ReturnType<typeof useActiveRunDefinition> | undefined;

    act(() => root.render(<Harness expose={(value) => { observed = value; }} runId="run-1" />));
    expect(observed).toEqual({ definition: null, error: false, loading: true });

    await act(async () => resolveResponse(new Response(JSON.stringify({ definition: definition(), read_model: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })));
    expect(observed?.definition?.book_scale_plan.total_chapters).toBe(3);
    expect(observed?.loading).toBe(false);
  });

  it('reports failure without inventing a fallback definition', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })));
    let observed: ReturnType<typeof useActiveRunDefinition> | undefined;

    await act(async () => root.render(<Harness expose={(value) => { observed = value; }} runId="run-1" />));
    expect(observed).toEqual({ definition: null, error: true, loading: false });
  });
});

function definition(): GraphRunDefinition {
  return {
    architecture_version: 'phase26-vnext',
    run_id: 'run-1',
    project_id: 'project-1',
    workflow_revision: 'phase26-vnext',
    quality_mode: 'balanced',
    inputs: {},
    book_scale_plan: buildBookScalePlan('total_chapters', 3),
    provider_bindings: {},
    cover_asset_binding: {
      provider_profile_id: 'image',
      model: 'gpt-image-2',
      candidate_count: 1,
      size: '1024x1536',
      quality: 'medium',
      timeout_seconds: 180,
      failure_policy: 'fail_run',
    },
    export_preferences: { format: 'zip', author: '', version_note: '' },
    created_at: '2026-08-11T00:00:00Z',
  };
}
