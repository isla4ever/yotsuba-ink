// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ButtonLoadingIndicator } from './ButtonLoadingIndicator';
import { LoadingButton } from './LoadingButton';
import { LoadingOverlay } from './LoadingOverlay';
import { ManuscriptLoadingIndicator } from './ManuscriptLoadingIndicator';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('Loading system', () => {
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

  it('keeps async button semantics explicit and stable', () => {
    act(() => root.render(<LoadingButton loading loadingLabel="正在保存">保存当前稿</LoadingButton>));

    const button = container.querySelector('button');
    expect(button?.disabled).toBe(true);
    expect(button?.getAttribute('aria-busy')).toBe('true');
    expect(button?.dataset.loading).toBe('true');
    expect(button?.querySelector('.nw-loading-button-content')?.textContent).toBe('保存当前稿');
    expect(button?.querySelector('.nw-loading-button-state')?.textContent).toContain('正在保存');
    expect(button?.querySelector('.nw-button-loader')).not.toBeNull();
  });

  it('generates collision-free SVG references for concurrent buttons', () => {
    act(() => root.render(<><ButtonLoadingIndicator /><ButtonLoadingIndicator /></>));

    const ids = Array.from(container.querySelectorAll('[id]')).map((node) => node.id);
    expect(ids).toHaveLength(36);
    expect(new Set(ids).size).toBe(ids.length);

    const urlReferences = Array.from(container.querySelectorAll('[filter], [mask], [fill]'))
      .flatMap((node) => ['filter', 'mask', 'fill'].map((attribute) => node.getAttribute(attribute)))
      .filter((value): value is string => Boolean(value?.startsWith('url(#')));
    expect(urlReferences.length).toBeGreaterThan(0);
    urlReferences.forEach((reference) => {
      const targetId = reference.slice(5, -1);
      expect(container.querySelector(`[id="${targetId}"]`)).not.toBeNull();
    });
  });

  it('renders the six-sheet manuscript indicator and an announced overlay', () => {
    act(() => root.render(
      <LoadingOverlay detail="正在读取阶段产物" title="恢复创作现场">
        <span>读取 Wiki</span>
      </LoadingOverlay>,
    ));

    expect(container.querySelectorAll('.nw-manuscript-loader-page')).toHaveLength(6);
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(container.querySelector('[role="status"]')?.textContent).toContain('恢复创作现场');
    expect(container.querySelector('[role="status"]')?.textContent).toContain('读取 Wiki');
  });

  it('offers a compact manuscript variant for panel-level waits', () => {
    act(() => root.render(<ManuscriptLoadingIndicator size="compact" />));
    expect(container.querySelector('.nw-manuscript-loader.is-compact')).not.toBeNull();
  });
});
