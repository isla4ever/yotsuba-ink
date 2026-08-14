// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { WorkflowDefinition, WorkflowStage } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { StageDecisionControls } from './StageDecisionControls';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const stage: WorkflowStage = {
  id: 'brief',
  label: '创作立项',
  type: 'brief',
} as WorkflowStage;

const workflow: WorkflowDefinition = {
  id: 'workflow',
  quality_mode: 'balanced',
  nodes: [stage],
} as WorkflowDefinition;

describe('StageDecisionControls', () => {
  it('exposes Brief accept and regenerate actions for its LangGraph interrupt', async () => {
    const confirm = vi.fn(async () => true);
    const regenerate = vi.fn();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <StageDecisionControls
          completed
          events={[runEvent('decision.required', { stage_id: 'brief', node_id: 'brief.human_decision', payload: { decision_id: 'decision-1' } })]}
          onConfirmStageArtifact={confirm}
          onRegenerateStageDraft={regenerate}
          stage={stage}
          workflow={workflow}
        />,
      );
    });

    expect(container.textContent).toContain('确认定稿');
    expect(container.textContent).toContain('换一稿');
    const buttons = Array.from(container.querySelectorAll('button'));
    const confirmButton = buttons.find((button) => button.textContent?.includes('确认定稿'));
    expect(confirmButton?.hasAttribute('disabled')).toBe(false);

    await act(async () => {
      confirmButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(confirm).toHaveBeenCalledTimes(1);
    root.unmount();
    container.remove();
  });
});
