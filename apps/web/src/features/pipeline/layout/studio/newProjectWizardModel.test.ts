import { describe, expect, it } from 'vitest';
import {
  initialWizardState,
  selectableTemplates,
  templateSummaryLine,
  wizardBack,
  wizardCanSubmit,
  wizardContinue,
  wizardNeedsTemplateStep,
  wizardSelectTemplate,
  wizardWithBasics,
} from './newProjectWizardModel';
import type { WorkflowDefinition } from '../../contracts';

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

describe('new-project wizard flow', () => {
  it('blocks step 1 → 2 without a title and proceeds once it is filled', () => {
    let state = initialWizardState();
    state = wizardContinue(state);
    expect(state.step).toBe('basics');
    expect(state.error).toBe('请先填写书名。');

    state = wizardWithBasics(state, { title: '雾城异闻' });
    expect(state.error).toBe('');
    state = wizardContinue(state);
    expect(state.step).toBe('template');
  });

  it('starts on the default template, supports reselect/back, and gates submission', () => {
    let state = wizardWithBasics(initialWizardState(), { title: '雾城异闻', summary: '一句概要' });
    expect(wizardCanSubmit(state)).toBe(false); // still on step 1
    state = wizardContinue(state);
    expect(state.templateId).toBe('default-novel-workflow');
    expect(wizardCanSubmit(state)).toBe(true);

    state = wizardSelectTemplate(state, 'wf-template-a');
    expect(state.templateId).toBe('wf-template-a');
    expect(wizardCanSubmit({ ...state, submitting: true })).toBe(false);

    state = wizardBack(state);
    expect(state.step).toBe('basics');
    expect(state.title).toBe('雾城异闻');
  });

  it('skips the template step when there is no real template choice (B4)', () => {
    const onlyDefault = [workflow({ id: 'default-novel-workflow', name: '默认工作流' })];
    expect(wizardNeedsTemplateStep(onlyDefault)).toBe(false);
    expect(wizardNeedsTemplateStep([])).toBe(false); // list still loading → default applies
    expect(wizardNeedsTemplateStep([...onlyDefault, workflow({ id: 'wf-a', is_template: true })])).toBe(true);

    // Single-template continue lands submit-ready with that template selected.
    let state = wizardWithBasics(initialWizardState(), { title: '雾城异闻' });
    state = wizardContinue(state, [workflow({ id: 'wf-only', name: '唯一模板', is_template: true })]);
    expect(state.templateId).toBe('wf-only');
    expect(wizardCanSubmit(state)).toBe(true);

    // The empty-title guard still runs before any skip.
    expect(wizardContinue(initialWizardState(), onlyDefault).error).toBe('请先填写书名。');

    // Multi-template lists keep the selection step with the default preselected.
    let multi = wizardWithBasics(initialWizardState(), { title: '雾城异闻' });
    multi = wizardContinue(multi, [...onlyDefault, workflow({ id: 'wf-a', is_template: true })]);
    expect(multi.step).toBe('template');
    expect(multi.templateId).toBe('default-novel-workflow');
  });

  it('offers is_template workflows plus the always-present default, default first', () => {
    const list = selectableTemplates([
      workflow({ id: 'wf-proj-1', name: '作品专属', is_template: false }),
      workflow({ id: 'wf-b', name: 'B 模板', is_template: true }),
      workflow({ id: 'default-novel-workflow', name: '默认工作流' }),
      workflow({ id: 'wf-a', name: 'A 模板', is_template: true }),
    ]);
    expect(list.map((item) => item.id)).toEqual(['default-novel-workflow', 'wf-a', 'wf-b']);
    expect(templateSummaryLine(workflow({ nodes: [{ id: 'info' } as WorkflowDefinition['nodes'][number]] }))).toBe('平衡档 · 1 个阶段');
  });
});
