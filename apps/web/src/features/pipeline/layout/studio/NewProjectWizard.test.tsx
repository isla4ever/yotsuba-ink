import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ProjectRecord, WorkflowDefinition } from '../../contracts';
import { NewProjectWizard } from './NewProjectWizard';

function workflow(overrides: Partial<WorkflowDefinition>): WorkflowDefinition {
  return {
    id: 'wf-x',
    name: '模板',
    version: '1',
    global_inputs: [],
    provider_profiles: [],
    prompt_templates: [],
    quality_mode: 'balanced',
    nodes: [],
    edges: [],
    ...overrides,
  };
}

function render(templates: WorkflowDefinition[]) {
  return renderToStaticMarkup(
    <NewProjectWizard
      open
      templates={templates}
      onClose={() => undefined}
      onCreate={() => Promise.resolve({} as ProjectRecord)}
      onCreated={() => undefined}
    />,
  );
}

describe('NewProjectWizard (Phase 12 B4/E8)', () => {
  it('collapses to a single create step when only the default template exists', () => {
    const html = render([workflow({ id: 'default-novel-workflow', name: '默认工作流' })]);

    expect(html).toContain('新建作品');
    expect(html).not.toContain('第 1 步 / 共 2 步');
    expect(html).toContain('创建并进入作品');
    expect(html).not.toContain('下一步');
  });

  it('keeps the two-step flow when there is a real template choice', () => {
    const html = render([
      workflow({ id: 'default-novel-workflow', name: '默认工作流' }),
      workflow({ id: 'wf-a', name: '自定义模板', is_template: true }),
    ]);

    expect(html).toContain('第 1 步 / 共 2 步');
    expect(html).toContain('下一步');
    expect(html).not.toContain('创建并进入作品');
  });

  it('submits through a form so Enter in the title field advances (E8)', () => {
    const html = render([workflow({ id: 'default-novel-workflow', name: '默认工作流' })]);

    expect(html).toContain('<form');
    expect(html).toContain('type="submit"');
    expect(html).toContain('studio-wizard-title');
  });

});
