import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { SetupStep } from '../contracts';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { GuidedSetupWorkbench } from './GuidedSetupWorkbench';

function steps(blockStory = false): SetupStep[] {
  return [
    {
      id: 'story', label: '故事起点', status: blockStory ? 'blocked' : 'complete', summary: '悬疑 · 80-120 万字',
      issues: blockStory
        ? [{ code: 'story_core_concept_missing', label: '请填写核心创意/冲突', severity: 'blocking', target: { stepId: 'story', fieldId: 'setup-story-core_concept' } }]
        : [],
    },
    { id: 'review', label: '确认启动', status: 'complete', summary: '智能参考 · 平衡', issues: [] },
  ];
}

function render(stepList: SetupStep[]) {
  return renderToStaticMarkup(
    <GuidedSetupWorkbench
      knowledgeDocuments={[]}
      saveStatus="saved"
      steps={stepList}
      workflow={defaultWorkflow}
      onOpenKnowledgeManager={() => undefined}
      onQualityModeChange={() => undefined}
      onSaveAndExit={() => undefined}
      onStageChange={() => undefined}
      onStart={() => Promise.resolve()}
    />,
  );
}

describe('GuidedSetupWorkbench', () => {
  it('wraps the step panel in a form so Enter advances, with footer actions submitting it', () => {
    const html = render(steps());

    expect(html).toContain('id="guided-setup-form"');
    expect(html).toContain('form="guided-setup-form"');
    expect(html).toContain('type="submit"');
    // 稍后继续 replaces the misleading save-labelled exit.
    expect(html).toContain('稍后继续');
    expect(html).not.toContain('暂时离开');
  });

  it('renders creative preparation without embedding pipeline service configuration', () => {
    const html = render(steps());

    expect(html).toContain('故事起点');
    expect(html).not.toContain('连接 AI 服务');
    expect(html).toContain('确认启动');
    expect(html).toContain('1/2');
    expect(html).not.toContain('创作依据');
    expect(html).not.toContain('质量方式');
  });
});
