import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ProjectRecord, WorkflowDefinition } from '../../contracts';
import { defaultWorkflowId, officialFastWorkflowId } from '../../lib/officialWorkflows';
import { NewProjectWizard } from './NewProjectWizard';

function workflow(id: string, name: string): WorkflowDefinition {
  return {
    architecture_version: 'phase27-vnext',
    id,
    name,
    version: '1',
    is_template: true,
    global_inputs: [],
    provider_profiles: [],
    prompt_templates: [],
    quality_mode: 'balanced',
    nodes: [],
    edges: [],
  };
}

function render(templates: WorkflowDefinition[], initialTemplateId = '') {
  return renderToStaticMarkup(
    <NewProjectWizard
      initialTemplateId={initialTemplateId}
      open
      templates={templates}
      onClose={() => undefined}
      onConfigure={() => Promise.resolve()}
      onCreate={() => Promise.resolve({} as ProjectRecord)}
      onCreated={() => undefined}
    />,
  );
}

describe('NewProjectWizard', () => {
  it('always starts by selecting a workflow, even when only one template is loaded', () => {
    const html = render([workflow(defaultWorkflowId, 'DeepSeek 平衡创作流水线')]);
    expect(html).toContain('第 1 步 / 共 2 步');
    expect(html).toContain('先确定创作流水线');
    expect(html).toContain('下一步：填写创作想法');
  });

  it('shows official choices and the configure-for-this-book action', () => {
    const html = render([
      workflow(officialFastWorkflowId, 'DeepSeek 极速创作流水线'),
      workflow(defaultWorkflowId, 'DeepSeek 平衡创作流水线'),
    ]);
    expect(html).toContain('推荐');
    expect(html).toContain('官方');
    expect(html).toContain('基于「DeepSeek 平衡创作流水线」配置本书');
  });

  it('recognizes a one-time workflow returned from the configuration page', () => {
    const html = render([], 'wf-once-123');
    expect(html).toContain('本书专用创作流水线');
    expect(html).toContain('已完成一次性配置');
  });
});
