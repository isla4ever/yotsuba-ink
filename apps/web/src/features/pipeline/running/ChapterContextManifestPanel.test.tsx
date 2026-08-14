// @vitest-environment happy-dom

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ChapterContextManifestPanel } from './ChapterContextManifestPanel';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('ChapterContextManifestPanel', () => {
  it('renders useful summaries without exposing hashes or raw JSON', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const record = {
      run_id: 'run-1', manifest_id: `manifest-${'a'.repeat(64)}`, chapter_id: 'chapter-1', attempt: 1,
      manifest: {
        task: 'chapter-1', required: ['detail.chapter'], optional: [], forbidden: ['full_canon'],
        snippets: [{ ref: 'detail.chapter', purpose: 'chapter_script', text: '{"purpose":"取证"}', source_hash: 'b'.repeat(64) }],
        budget: { input_chars: 16, output_tokens: 1200 }, manifest_hash: 'c'.repeat(64),
      }, created_at: '2026-08-12T00:00:00Z',
    } as const;

    act(() => root.render(<ChapterContextManifestPanel detail error="" record={record} status="ready" />));

    expect(container.textContent).toContain('本章施工图');
    expect(container.textContent).toContain('必须读取');
    expect(container.textContent).toContain('明确禁止');
    expect(container.textContent).not.toContain(record.manifest.manifest_hash);
    expect(container.textContent).not.toContain(record.manifest.snippets[0].text);
    act(() => root.unmount());
  });

  it('opens the detail sheet from the compact summary command', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const onOpen = vi.fn();
    act(() => root.render(<ChapterContextManifestPanel error="暂不可用" onOpen={onOpen} record={null} status="unavailable" />));
    act(() => container.querySelector<HTMLButtonElement>('button')?.click());
    expect(onOpen).toHaveBeenCalledOnce();
    act(() => root.unmount());
  });
});
