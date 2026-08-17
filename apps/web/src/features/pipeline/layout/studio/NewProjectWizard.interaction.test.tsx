// @vitest-environment happy-dom

import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ProjectRecord, WorkflowDefinition } from '../../contracts';
import { overlayExitDurationMs } from '../../lib/motion';
import { NewProjectWizard } from './NewProjectWizard';
import { defaultWorkflowId } from '../../lib/officialWorkflows';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const defaultWorkflow: WorkflowDefinition = {
  architecture_version: 'phase27-vnext',
  id: defaultWorkflowId,
  name: '默认工作流',
    version: '1',
    is_template: true,
  global_inputs: [],
  provider_profiles: [],
  prompt_templates: [],
  quality_mode: 'balanced',
  nodes: [],
  edges: [],
};

describe('NewProjectWizard overlay interaction', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.useFakeTimers();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    document.body.style.overflow = '';
    vi.useRealTimers();
  });

  it('installs Escape and focus-return handling when opened after the closed state', () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)} type="button">打开新建作品</button>
          <NewProjectWizard
            open={open}
            templates={[defaultWorkflow]}
            onClose={() => setOpen(false)}
            onConfigure={() => Promise.resolve()}
            onCreate={() => Promise.resolve({} as ProjectRecord)}
            onCreated={() => undefined}
          />
        </>
      );
    }

    act(() => root.render(<Harness />));
    const opener = container.querySelector('button');
    expect(opener).not.toBeNull();
    opener?.focus();
    act(() => opener?.click());

    const selectedPipeline = document.querySelector<HTMLButtonElement>('[role="radio"][aria-checked="true"]');
    expect(selectedPipeline).not.toBeNull();
    expect(document.body.style.overflow).toBe('hidden');
    expect(container.inert).toBe(true);
    expect(container.getAttribute('aria-hidden')).toBe('true');
    act(() => vi.advanceTimersByTime(16));
    expect(document.activeElement).toBe(selectedPipeline);

    act(() => opener?.focus());
    expect(document.activeElement).toBe(selectedPipeline);

    act(() => {
      selectedPipeline?.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, key: 'Escape' }));
    });
    act(() => vi.advanceTimersByTime(overlayExitDurationMs.dialog));

    expect(document.querySelector('[role="dialog"][aria-label="新建作品"]')).toBeNull();
    expect(document.body.style.overflow).toBe('');
    expect(container.inert).toBe(false);
    expect(container.hasAttribute('aria-hidden')).toBe(false);
    expect(document.activeElement).toBe(opener);
  });
});
