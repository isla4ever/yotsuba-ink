// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stages } from '../../state/defaultWorkflow';
import { WorkflowTemplateDeck } from './WorkflowTemplateDeck';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('WorkflowTemplateDeck', () => {
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

  it('renders the stage manuscript stack and announces the active configuration', () => {
    act(() => root.render(
      <WorkflowTemplateDeck activeStageId="brief" qualityMode="balanced" stages={stages} onSelect={() => undefined} />,
    ));

    expect(container.textContent).toContain('八阶段稿件栈');
    expect(container.textContent).toContain('创作契约、世界规则与长度包络');
    expect(container.querySelectorAll('ol > li')).toHaveLength(8);
    expect(container.querySelector('[aria-current="step"]')?.getAttribute('aria-label')).toContain('创作立项定稿');
    expect(container.querySelector('.artifact-deck-pedestal')).not.toBeNull();
    expect(container.querySelector('.artifact-deck-branchmap')).toBeNull();
  });

  it('selects a stage through its real button control', () => {
    const onSelect = vi.fn();
    act(() => root.render(
      <WorkflowTemplateDeck activeStageId="brief" qualityMode="balanced" stages={stages} onSelect={onSelect} />,
    ));

    const detail = [...container.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.getAttribute('aria-label')?.includes('章节施工图'));
    expect(detail).toBeDefined();
    act(() => detail?.click());
    expect(onSelect).toHaveBeenCalledWith('detail');
    expect(detail?.getAttribute('aria-label')).toContain('第 5 阶段');
  });
});
