// @vitest-environment happy-dom

import { act, createElement, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import { createSelectionAnchor, useStageSelectionCapture } from './useStageSelectionCapture';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('createSelectionAnchor', () => {
  it('converts browser UTF-16 offsets to Python-compatible Unicode offsets', async () => {
    const fieldValue = '序章😀主角拒绝签字，随后主角拒绝离场';
    const selectedText = '主角拒绝离场';
    const selectionStart = fieldValue.lastIndexOf(selectedText);
    const selectionEnd = selectionStart + selectedText.length;

    const anchor = await createSelectionAnchor({
      fieldPath: 'content',
      fieldValue,
      selectionEnd,
      selectionStart,
      sourceRef: 'chapter-1-v1',
      stageId: 'text',
      unitRef: 'chapter-1',
    });

    expect(anchor.selection_start).toBe(Array.from(fieldValue.slice(0, selectionStart)).length);
    expect(anchor.selection_end).toBe(anchor.selection_start + Array.from(selectedText).length);
    expect(anchor.selected_char_count).toBe(Array.from(selectedText).length);
    expect(anchor.selected_text).toBe(selectedText);
    expect(anchor.field_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(anchor.selected_text_hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('keeps a bounded Unicode-safe preview for long selections', async () => {
    const fieldValue = `${'潮声'.repeat(45)}😀终点`;
    const anchor = await createSelectionAnchor({
      fieldPath: 'ending',
      fieldValue,
      selectionEnd: fieldValue.length,
      selectionStart: 0,
      sourceRef: 'spine-v1',
      stageId: 'spine',
      unitRef: 'artifact',
    });

    expect(Array.from(anchor.preview.replace(/\.\.\.$/u, '')).length).toBe(80);
    expect(anchor.preview.endsWith('...')).toBe(true);
  });

  it('keeps an anchored stage selection while the collaboration composer receives focus', async () => {
    const container = document.createElement('div');
    document.body.append(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(createElement(SelectionHarness));
    });
    const stageField = container.querySelector<HTMLTextAreaElement>('[data-collaboration-field-path="ending"]');
    const composer = container.querySelector<HTMLTextAreaElement>('[aria-label="作者协作输入"]');
    expect(stageField).not.toBeNull();
    expect(composer).not.toBeNull();

    await act(async () => {
      stageField?.focus();
      stageField?.setSelectionRange(0, stageField.value.length);
      stageField?.dispatchEvent(new Event('select', { bubbles: true }));
    });
    await waitForText(container, '主角公开证据');
    expect(container.querySelector('[data-testid="selection-preview"]')?.textContent)
      .toBe('主角公开证据');

    await act(async () => {
      composer?.focus();
      composer?.setSelectionRange(0, 0);
      composer?.dispatchEvent(new Event('select', { bubbles: true }));
    });
    await waitForText(container, '主角公开证据');
    expect(container.querySelector('[data-testid="selection-preview"]')?.textContent)
      .toBe('主角公开证据');

    act(() => root.unmount());
    container.remove();
  });
});

function SelectionHarness() {
  const rootRef = useRef<HTMLDivElement>(null);
  const { selection } = useStageSelectionCapture({
    enabled: true,
    rootRef,
    sourceRef: 'spine-candidate-1',
    stageId: 'spine',
  });
  return createElement('div', { ref: rootRef },
    createElement('textarea', {
      'data-collaboration-field-path': 'ending',
      'data-collaboration-unit': 'artifact',
      defaultValue: '主角公开证据',
    }),
    createElement('textarea', { 'aria-label': '作者协作输入' }),
    createElement('output', { 'data-testid': 'selection-preview' }, selection?.selected_text ?? ''),
  );
}

async function waitForText(container: HTMLElement, expected: string) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (container.querySelector('[data-testid="selection-preview"]')?.textContent === expected) return;
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });
  }
  throw new Error(`Selection preview did not become ${expected}`);
}
