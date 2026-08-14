// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useChapterContextManifest } from './useChapterContextManifest';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

function Harness({ enabled = true, expose, revision = 1, runId = 'run-1' }: {
  enabled?: boolean;
  expose: (value: ReturnType<typeof useChapterContextManifest>) => void;
  revision?: number;
  runId?: string;
}) {
  expose(useChapterContextManifest(runId, revision, enabled));
  return null;
}

describe('useChapterContextManifest', () => {
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

  it('follows the current read-model reference to the immutable sidecar', async () => {
    const record = manifestRecord();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ read_model: { context_manifest_ref: record.manifest_id } }))
      .mockResolvedValueOnce(jsonResponse(record));
    vi.stubGlobal('fetch', fetchMock);
    let observed: ReturnType<typeof useChapterContextManifest> | undefined;

    await act(async () => root.render(<Harness expose={(value) => { observed = value; }} />));

    expect(observed).toEqual({ record, status: 'ready', error: '' });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/runs/run-1',
      `/api/runs/run-1/context-manifests/${record.manifest_id}`,
    ]);
  });

  it('reports a missing reference without inventing manifest content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ read_model: { context_manifest_ref: '' } })));
    let observed: ReturnType<typeof useChapterContextManifest> | undefined;

    await act(async () => root.render(<Harness expose={(value) => { observed = value; }} />));

    expect(observed?.status).toBe('unavailable');
    expect(observed?.record).toBeNull();
    expect(observed?.error).toContain('尚未生成');
  });

  it('does not read the Run outside the text stage', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    let observed: ReturnType<typeof useChapterContextManifest> | undefined;

    await act(async () => root.render(<Harness enabled={false} expose={(value) => { observed = value; }} />));

    expect(observed).toEqual({ record: null, status: 'idle', error: '' });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

function manifestRecord() {
  return {
    run_id: 'run-1',
    manifest_id: `manifest-${'a'.repeat(64)}`,
    chapter_id: 'chapter-1',
    attempt: 1,
    manifest: {
      task: 'chapter-1',
      required: ['detail.chapter', 'cast.subjects'],
      optional: [],
      forbidden: ['full_canon'],
      snippets: [{ ref: 'detail.chapter', purpose: 'chapter_script', text: '本章施工图', source_hash: 'b'.repeat(64) }],
      budget: { input_chars: 5, output_tokens: 1200 },
      manifest_hash: 'c'.repeat(64),
    },
    created_at: '2026-08-12T00:00:00Z',
  } as const;
}
