import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { SetupStep, WorkflowStage } from '../contracts';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { reviewReferenceCardId } from '../lib/setupProgress';
import { SetupReviewSection, withReferenceSummary } from './SetupReviewSection';

const infoStage = defaultWorkflow.nodes.find((stage) => stage.type === 'info') as WorkflowStage;

function completeSteps(): SetupStep[] {
  return [
    { id: 'story', label: '故事起点', status: 'complete', summary: '悬疑 · 80-120 万字', issues: [] },
    { id: 'ai-service', label: '连接 AI 服务', status: 'complete', summary: '2 项服务检查通过', issues: [] },
    { id: 'review', label: '确认启动', status: 'complete', summary: '智能参考 · 平衡', issues: [] },
  ];
}

function render(steps: SetupStep[], stage: WorkflowStage = infoStage) {
  return renderToStaticMarkup(
    <SetupReviewSection
      knowledgeDocuments={[]}
      stage={stage}
      steps={steps}
      workflow={defaultWorkflow}
      onOpenKnowledgeManager={() => undefined}
      onQualityModeChange={() => undefined}
      onStageChange={() => undefined}
      onStepRequest={() => undefined}
    />,
  );
}

describe('SetupReviewSection (Phase 12 A4 确认启动页)', () => {
  it('shows collapsed default cards, the readiness ledger, and the launch-ready status', () => {
    const html = render(completeSteps());

    expect(html).toContain('已用默认');
    expect(html).toContain('参考方式');
    expect(html).toContain('创作模式');
    // The mode card quotes qualityModeProfiles for the one-line difference.
    expect(html).toContain('平衡');
    expect(html).toContain('逐阶段与逐章确认');
    // Ledger lists the real steps with edit affordances.
    expect(html).toContain('修改故事起点');
    expect(html).toContain('修改连接 AI 服务');
    expect(html).toContain('可以开始创作');
    // Cards start collapsed when nothing needs fixing.
    expect(html).not.toContain('setup-review-reference-summary');
  });

  it('auto-expands the reference card for its own issue and shows the editable summary with its destination note', () => {
    const steps = completeSteps();
    steps[2] = {
      ...steps[2],
      status: 'blocked',
      issues: [{
        code: 'knowledge_document_unavailable',
        label: '1 份已选资料当前不可用',
        severity: 'blocking',
        target: { stepId: 'review', fieldId: reviewReferenceCardId },
      }],
    };
    const stage = withReferenceSummary(infoStage, '检索意图：群像悬疑结构参考。');
    const html = render(steps, stage);

    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain('id="setup-review-reference-summary"');
    expect(html).toContain('检索意图：群像悬疑结构参考。');
    expect(html).toContain('该摘要将进入创作立项阶段的输入');
    expect(html).toContain('还有 1 项启动条件需要处理');
  });

  it('falls back to the balanced profile copy when the stored mode is out of contract', () => {
    const steps = completeSteps();
    steps[2] = {
      ...steps[2],
      status: 'blocked',
      issues: [{
        code: 'quality_mode_missing',
        label: '请选择创作模式',
        severity: 'blocking',
        target: { stepId: 'review', fieldId: 'setup-review-creation-mode' },
      }],
    };
    const html = renderToStaticMarkup(
      <SetupReviewSection
        knowledgeDocuments={[]}
        stage={infoStage}
        steps={steps}
        workflow={{ ...defaultWorkflow, quality_mode: 'legacy' as typeof defaultWorkflow.quality_mode }}
        onOpenKnowledgeManager={() => undefined}
        onQualityModeChange={() => undefined}
        onStageChange={() => undefined}
        onStepRequest={() => undefined}
      />,
    );

    expect(html).toContain('请选择创作模式');
    expect(html).toContain('平衡');
  });

  it('writes summary edits back to the info stage reference_summary input', () => {
    const next = withReferenceSummary(infoStage, '手动整理的参考要点');
    expect(next.input_schema.find((field) => field.key === 'reference_summary')?.default).toBe('手动整理的参考要点');
    // The source stage stays untouched (autosave diffing depends on immutability).
    expect(infoStage.input_schema.find((field) => field.key === 'reference_summary')?.default).toBe('');
  });
});
