// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CoverAssetRecord } from '../contracts';
import { CoverStageViewVnext } from './CoverStageViewVnext';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact = {
  brief: {
    concept: '雾港里的记忆缺口',
    image_prompt: '旧广播塔、雾与人物剪影',
    palette: ['#111827', '#d4c8b8'],
    negative_constraints: ['不渲染文字'],
  },
  selected_asset_id: '',
};

describe('CoverStageViewVnext', () => {
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

  it('loads image candidates and selects one without exposing an asset-id field', async () => {
    const assets = [coverAsset('cover-a', 1), coverAsset('cover-b', 2)];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      run_id: 'run-1', generation_attempt: 1, items: assets,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
    const onArtifactChange = vi.fn();

    await act(async () => {
      root.render(<CoverStageViewVnext
        onArtifactChange={onArtifactChange}
        readOnly={false}
        result={JSON.stringify(artifact)}
        runId="run-1"
        sourceResult={JSON.stringify(artifact)}
      />);
    });

    expect(container.querySelectorAll('.vnext-cover-candidate-rail button')).toHaveLength(2);
    expect(container.querySelector('input')).toBeNull();
    expect(Array.from(container.querySelectorAll('textarea')).every((field) => field.readOnly)).toBe(true);
    const second = container.querySelectorAll<HTMLButtonElement>('.vnext-cover-candidate-rail button')[1];
    act(() => second.click());
    expect(onArtifactChange).toHaveBeenLastCalledWith({ ...artifact, selected_asset_id: 'cover-b' });
    expect(second.getAttribute('aria-pressed')).toBe('true');
  });

  it('keeps the brief locked when the immutable candidate set cannot be verified', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('asset store unavailable')));
    const onArtifactChange = vi.fn();

    await act(async () => {
      root.render(<CoverStageViewVnext
        onArtifactChange={onArtifactChange}
        readOnly={false}
        result={JSON.stringify(artifact)}
        runId="run-1"
        sourceResult={JSON.stringify(artifact)}
      />);
    });

    expect(container.textContent).toContain('资产不可用');
    expect(Array.from(container.querySelectorAll('textarea')).every((field) => field.readOnly)).toBe(true);
    expect(onArtifactChange).not.toHaveBeenCalled();
  });
});

function coverAsset(assetId: string, candidateIndex: number): CoverAssetRecord {
  return {
    asset_id: assetId,
    run_id: 'run-1',
    operation_key: `run-1:cover:image:1:candidate:${candidateIndex}`,
    candidate_index: candidateIndex,
    generation_attempt: 1,
    sha256: 'a'.repeat(64),
    mime_type: 'image/png',
    extension: 'png',
    width: 1024,
    height: 1536,
    size_bytes: 100,
    provider_asset_id: '',
    revised_prompt: '',
    created_at: '2026-08-11T00:00:00Z',
    content_url: `/api/runs/run-1/cover-assets/${assetId}`,
  };
}
