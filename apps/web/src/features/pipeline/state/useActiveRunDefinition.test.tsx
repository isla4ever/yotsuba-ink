// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphRunDefinition } from '../contracts';
import {
  frozenCoverAssetBindingFixture,
  frozenProviderBindingsFixture,
} from '../contracts/runTestFixtures';
import { scaleProfileFromLengthEnvelope } from '../lib/narrativeScale';
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
    expect(observed?.definition?.scale_profile.word_target_soft).toBe(100_000);
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
    architecture_version: 'phase27-vnext',
    run_id: 'run-1',
    project_id: 'project-1',
    workflow_id: 'workflow-phase27',
    workflow_revision: 'phase27-vnext',
    workflow_digest: 'a'.repeat(64),
    quality_mode: 'balanced',
    inputs: {},
    scale_profile: scaleProfileFromLengthEnvelope({
      word_target_soft: 100_000,
    }),
    provider_bindings: frozenProviderBindingsFixture(),
    cover_asset_binding: frozenCoverAssetBindingFixture(),
    export_preferences: { format: 'zip', author: '', version_note: '' },
    created_at: '2026-08-11T00:00:00Z',
  };
}
