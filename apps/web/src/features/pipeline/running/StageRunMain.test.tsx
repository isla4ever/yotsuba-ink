// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { WorkflowDefinition, WorkflowStage } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { StageRunMain } from './StageRunMain';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const spineStage = {
  id: 'spine',
  label: '故事脊柱',
  type: 'spine',
} as WorkflowStage;

const briefStage = {
  id: 'brief',
  label: '创作立项',
  type: 'brief',
} as WorkflowStage;

const workflow = {
  id: 'workflow',
  quality_mode: 'balanced',
  nodes: [spineStage],
} as WorkflowDefinition;

describe('StageRunMain', () => {
  it('submits the edited Brief bound to the immutable candidate source', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const artifact = {
      title: '潮汐公证员',
      premise: '盐库公证员从受潮记忆里听见失踪弟弟的求救。',
      promise: '用可回溯物证追查十年前事故。',
      world_rules: ['每修复一段记忆，现实中一名相关证人会遗忘同一件事。'],
      theme: '公共证据与家庭共谋的代价。',
      ending_promise: '公开原始记录并回答弟弟的责任与去向。',
      voice: '克制、职业化、重程序细节。',
      length_envelope: { word_target_soft: 100_000 },
    };
    const events = [
      runEvent('decision.required', {
        sequence: 2,
        stage_id: 'brief',
        node_id: 'brief.human_decision',
        payload: { decision_id: 'brief-decision-1', artifact_ref: 'brief-candidate-1', domain_revision: 1 },
      }),
      runEvent('artifact.candidate_ready', {
        sequence: 1,
        stage_id: 'brief',
        node_id: 'brief.generate_candidate',
        payload: artifact,
        payload_ref: 'brief-candidate-1',
      }),
    ];
    const source = JSON.stringify(artifact);
    const edited = { ...artifact, title: '盐库遗证' };
    const change = vi.fn();
    const approve = vi.fn(async (_artifact: string) => true);
    const common = {
      activeRunId: 'run-brief-edit',
      events,
      onApproveBrief: approve,
      onConfirmStageArtifact: vi.fn(async () => true),
      onOpenRuntimePanel: vi.fn(),
      onRegenerateBrief: vi.fn(async () => true),
      onRegenerateStageDraft: vi.fn(),
      onStageArtifactDraftChange: change,
      runDefinition: null,
      stage: briefStage,
      workflow: { ...workflow, nodes: [briefStage] },
    };

    act(() => root.render(<StageRunMain {...common} />));
    const title = container.querySelector<HTMLInputElement>('input[value="潮汐公证员"]');
    expect(title).not.toBeNull();
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(title, edited.title);
      title?.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(change).toHaveBeenCalledWith('brief', source, JSON.stringify(edited, null, 2));

    act(() => root.render(
      <StageRunMain
        {...common}
        stageArtifactDraft={{ source, value: JSON.stringify(edited, null, 2) }}
        stageArtifactDraftStatus="saved"
      />,
    ));
    const confirm = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent?.includes('确认定稿'));
    expect(confirm).toBeDefined();
    await act(async () => { confirm?.click(); });
    expect(approve).toHaveBeenCalledOnce();
    expect(JSON.parse(approve.mock.calls[0]?.[0] ?? '{}')).toEqual(edited);

    act(() => root.unmount());
    container.remove();
  });

  it('does not report an artifact contract error while a replacement is generating', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const events = [
      runEvent('node.started', { stage_id: 'spine', node_id: 'spine.generate_candidate' }),
      runEvent('artifact.candidate_ready', {
        stage_id: 'spine',
        node_id: 'spine.generate_candidate',
        payload: { artifact_id: 'spine-candidate-1' },
      }),
    ];

    act(() => {
      root.render(
          <StageRunMain
            activeRunId="run-1"
            events={events}
          onApproveBrief={vi.fn(async () => true)}
          onConfirmStageArtifact={vi.fn(async () => true)}
          onOpenRuntimePanel={vi.fn()}
          onRegenerateBrief={vi.fn(async () => true)}
          onRegenerateStageDraft={vi.fn()}
          onStageArtifactDraftChange={vi.fn()}
          runDefinition={null}
          stage={spineStage}
          workflow={workflow}
        />,
      );
    });

    expect(container.textContent).toContain('故事脊柱正在生成');
    expect(container.textContent).not.toContain('阶段产物不是有效 JSON');
    expect(container.querySelector('[role="alert"]')).toBeNull();

    act(() => root.unmount());
    container.remove();
  });

  it('shows the current successful decision after historical regeneration failures', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const artifact = {
      turns: [{
        id: 'turn-1',
        cause: '母带被删除',
        change: '主角决定调查并在同一短篇转折中承担公开后果',
        progress_type: 'information',
        milestones: ['inciting', 'commitment', 'midpoint_reversal', 'crisis', 'climax', 'aftermath'],
      }],
      ending: '公开母带并承担记忆损失',
      open_questions: ['谁签署了删除令？'],
      progress_types: ['information'],
    };
    const events = [
      runEvent('decision.required', { sequence: 24, stage_id: 'spine', node_id: 'spine.human_decision' }),
      usageEvent(22, 15, 64603),
      runEvent('artifact.candidate_ready', { sequence: 19, stage_id: 'spine', node_id: 'spine.generate_candidate', payload: artifact }),
      runEvent('decision.resolved', { sequence: 17, stage_id: 'spine', node_id: 'spine.failure_decision' }),
      runEvent('decision.required', { sequence: 16, stage_id: 'spine', node_id: 'spine.failure_decision' }),
      runEvent('node.failed', {
        sequence: 15,
        stage_id: 'spine',
        node_id: 'spine.generate_candidate',
        payload: { message: '历史失败不应继续展示' },
      }),
      usageEvent(7, 7, 23918),
    ];

    act(() => {
      root.render(
          <StageRunMain
            activeRunId="run-1"
            events={events}
          onApproveBrief={vi.fn(async () => true)}
          onConfirmStageArtifact={vi.fn(async () => true)}
          onOpenRuntimePanel={vi.fn()}
          onRegenerateBrief={vi.fn(async () => true)}
          onRegenerateStageDraft={vi.fn()}
          onStageArtifactDraftChange={vi.fn()}
          runDefinition={null}
          stage={spineStage}
          workflow={workflow}
        />,
      );
    });

    expect(container.textContent).toContain('15 次调用 · 64,603 tokens');
    expect(container.textContent).toContain('本阶段已生成，等待人工定稿');
    expect(container.textContent).not.toContain('历史失败不应继续展示');
    expect(container.textContent).not.toContain('本次生成未通过阶段合同');

    act(() => root.unmount());
    container.remove();
  });
});

function usageEvent(sequence: number, providerOperations: number, totalTokens: number) {
  return runEvent('node.completed', {
    sequence,
    stage_id: 'spine',
    node_id: 'spine.validate_contract',
    payload: {
      provider_usage: {
        provider_operations: providerOperations,
        succeeded_operations: providerOperations,
        failed_operations: 0,
        pending_operations: 0,
        prompt_tokens: totalTokens,
        completion_tokens: 0,
        total_tokens: totalTokens,
        reasoning_tokens: 0,
      },
    },
  });
}
