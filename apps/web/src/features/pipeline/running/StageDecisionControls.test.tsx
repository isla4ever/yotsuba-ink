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
          stageArtifactDraftStatus="saved"
          workflow={workflow}
        />,
      );
    });

    expect(container.textContent).toContain('确认定稿');
    expect(container.textContent).toContain('换一稿');
    expect(container.textContent).toContain('已保存');
    const buttons = Array.from(container.querySelectorAll('button'));
    const confirmButton = buttons.find((button) => button.textContent?.includes('确认定稿'));
    expect(confirmButton?.hasAttribute('disabled')).toBe(false);

    await act(async () => {
      confirmButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(confirm).toHaveBeenCalledTimes(1);
    act(() => root.unmount());
    container.remove();
  });

  it('offers a new generation attempt without allowing the stale artifact to be committed', async () => {
    const retry = vi.fn();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <StageDecisionControls
          completed={false}
          events={[
            runEvent('decision.required', { stage_id: 'brief', node_id: 'brief.failure_decision', payload: { decision_id: 'failure-1' } }),
            runEvent('node.failed', { stage_id: 'brief', node_id: 'brief.generate_candidate' }),
          ]}
          onConfirmStageArtifact={vi.fn(async () => true)}
          onRegenerateStageDraft={retry}
          stage={stage}
          workflow={{ ...workflow, quality_mode: 'fast' }}
        />,
      );
    });

    expect(container.textContent).toContain('本次生成未通过阶段合同');
    expect(container.textContent).toContain('重试本阶段');
    const buttons = Array.from(container.querySelectorAll('button'));
    const retryButton = buttons.find((button) => button.textContent?.includes('重试本阶段'));
    expect(retryButton?.hasAttribute('disabled')).toBe(false);
    expect(buttons.find((button) => button.textContent?.includes('确认定稿'))?.hasAttribute('disabled')).toBe(true);

    await act(async () => {
      retryButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(retry).toHaveBeenCalledWith('brief', '', '');
    expect(document.querySelector('[aria-label="创作立项换一稿"]')).toBeNull();

    act(() => root.unmount());
    container.remove();
  });

  it('blocks acceptance for hard findings and opens an evidence-backed recommended revision', async () => {
    const regenerate = vi.fn();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <StageDecisionControls
          chapterId="chapter-1"
          completed
          events={[runEvent('decision.required', {
            stage_id: 'text',
            node_id: 'text.author_decision',
            chapter_id: 'chapter-1',
            payload: {
              decision_id: 'chapter-decision-1',
              allowed_actions: ['regenerate', 'cancel'],
              regeneration_limit: 1,
              regeneration_used: 0,
              reason: {
                blocking_findings: [{
                  claim: '正文让 24 小时后的事故在同一时段兑现',
                  code: 'time_rule_conflict',
                  evidence: '几分钟后撞击声响起',
                }],
                warning_findings: [],
              },
            },
          })]}
          onConfirmStageArtifact={vi.fn(async () => true)}
          onRegenerateStageDraft={regenerate}
          stage={{ ...stage, id: 'text', label: '正文生成', type: 'text' } as WorkflowStage}
          workflow={{ ...workflow, nodes: [], quality_mode: 'balanced' }}
        />,
      );
    });

    expect(container.textContent).toContain('当前稿不可定稿');
    expect(container.textContent).toContain('推荐换稿');
    const buttons = Array.from(container.querySelectorAll('button'));
    expect(buttons.find((button) => button.textContent?.includes('确认正文定稿'))?.hasAttribute('disabled')).toBe(true);

    await act(async () => {
      buttons.find((button) => button.textContent?.includes('推荐换稿'))
        ?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(document.body.textContent).toContain('审校证据');
    expect(document.body.textContent).toContain('几分钟后撞击声响起');
    expect(document.body.textContent).toContain('只修复以下审校问题');

    act(() => root.unmount());
    document.querySelector('[aria-label="正文生成换一稿"]')?.remove();
    container.remove();
  });

  it('keeps soft warnings non-blocking and shows an exhausted one-draft limit', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <StageDecisionControls
          completed
          events={[runEvent('decision.required', {
            stage_id: 'brief',
            node_id: 'brief.human_decision',
            payload: {
              decision_id: 'brief-decision-2',
              allowed_actions: ['accept', 'cancel'],
              regeneration_limit: 1,
              regeneration_used: 1,
              reason: { warning_findings: [{ claim: '节奏略慢', code: 'pacing', evidence: '解释段稍长' }] },
            },
          })]}
          onConfirmStageArtifact={vi.fn(async () => true)}
          onRegenerateStageDraft={vi.fn()}
          stage={stage}
          workflow={workflow}
        />,
      );
    });

    expect(container.textContent).toContain('可接受或定向换稿');
    expect(container.textContent).toContain('已换稿 1/1');
    expect(Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('确认定稿'))?.hasAttribute('disabled')).toBe(false);

    act(() => root.unmount());
    container.remove();
  });
});
