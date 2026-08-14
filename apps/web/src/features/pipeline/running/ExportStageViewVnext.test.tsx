// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExportStageViewVnext } from './ExportStageViewVnext';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact = {
  format: 'zip' as const,
  chapter_version_ids: ['chapter-1-v1-accepted', 'chapter-2-v1-accepted'],
  cover_asset_id: 'cover-a',
  metadata: { title: '雾港旧声', author: '', version_note: '' },
  volumes: [{ title: '雾港残响', chapter_count: 2 }],
};

describe('ExportStageViewVnext', () => {
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
  });

  it('edits delivery preferences while keeping authority references read-only', () => {
    const onArtifactChange = vi.fn();
    act(() => root.render(<ExportStageViewVnext
      deliveryRevision=""
      onArtifactChange={onArtifactChange}
      readOnly={false}
      result={JSON.stringify(artifact)}
      runId="run-1"
    />));

    const title = container.querySelector<HTMLInputElement>('input[value="雾港旧声"]');
    expect(title?.readOnly).toBe(true);
    expect(container.querySelector('input[value="cover-a"]')).toBeNull();
    expect(container.textContent).toContain('chapter-2-v1-accepted');
    expect(container.textContent).toContain('雾港残响');

    const markdown = Array.from(container.querySelectorAll<HTMLButtonElement>('.vnext-export-format button'))
      .find((button) => button.textContent?.includes('Markdown'));
    act(() => markdown?.click());
    expect(onArtifactChange).toHaveBeenLastCalledWith({ ...artifact, format: 'md' });
  });

  it('shows the immutable materialization receipt after Export commit', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{
        export_id: 'export-1',
        run_id: 'run-1',
        artifact_id: 'artifact-export',
        artifact_signature: 'b'.repeat(64),
        format: 'zip',
        chapter_version_ids: artifact.chapter_version_ids,
        cover_asset_id: artifact.cover_asset_id,
        metadata: artifact.metadata,
        filename: '雾港旧声.zip',
        media_type: 'application/zip',
        size_bytes: 2048,
        sha256: 'a'.repeat(64),
        created_at: '2026-08-11T00:00:00Z',
      }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    await act(async () => root.render(<ExportStageViewVnext
      deliveryRevision="event-export-committed"
      onArtifactChange={() => undefined}
      readOnly
      result={JSON.stringify(artifact)}
      runId="run-1"
    />));

    expect(container.querySelector('.vnext-export-receipt')?.textContent).toContain('雾港旧声.zip');
    expect(container.querySelector('.vnext-export-receipt')?.textContent).toContain('2.0 KB');
    expect(container.querySelector<HTMLButtonElement>('.vnext-export-receipt button')?.textContent).toContain('校验并下载');
  });
});
