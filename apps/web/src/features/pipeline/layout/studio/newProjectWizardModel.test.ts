import { describe, expect, it } from 'vitest';
import type { WorkflowDefinition, WorkflowStage } from '../../contracts';
import {
  initialWizardState,
  selectableTemplates,
  templateSummaryLine,
  wizardBack,
  wizardCanSubmit,
  wizardContinue,
  wizardSelectTemplate,
  wizardWithIdea,
} from './newProjectWizardModel';
import {
  defaultWorkflowId,
  officialDeepWorkflowId,
  officialFastWorkflowId,
} from '../../lib/officialWorkflows';

function stage(model = 'deepseek-v4-flash'): WorkflowStage {
  return {
    id: 'brief',
    type: 'brief',
    label: '创作立项',
    input_schema: [],
    prompt_template_id: 'prompt-brief',
    provider_profile_id: 'provider-deepseek-text',
    model_settings: { model, temperature: 0.7, max_tokens: 1000, top_p: 1, timeout_seconds: 60 },
  };
}

function workflow(overrides: Partial<WorkflowDefinition>): WorkflowDefinition {
  return {
    architecture_version: 'phase27-vnext',
    id: 'wf-x',
    name: '模板',
    version: '1',
    is_template: true,
    global_inputs: [],
    provider_profiles: [],
    prompt_templates: [],
    quality_mode: 'balanced',
    nodes: [stage()],
    edges: [],
    ...overrides,
  };
}

describe('new-project wizard flow', () => {
  it('starts with the recommended pipeline and always advances to the idea step', () => {
    let state = initialWizardState();
    expect(state.step).toBe('workflow');
    expect(state.templateId).toBe(defaultWorkflowId);

    state = wizardContinue(state);
    expect(state.step).toBe('idea');
    expect(wizardCanSubmit(state)).toBe(false);
  });

  it('requires a story idea, supports pipeline reselection, and preserves it when going back', () => {
    let state = wizardSelectTemplate(initialWizardState(), 'wf-template-a');
    state = wizardContinue(state);
    state = wizardWithIdea(state, '一名修表匠发现整座城市每天都会丢失一分钟。');
    expect(wizardCanSubmit(state)).toBe(true);
    expect(wizardCanSubmit({ ...state, submitting: true })).toBe(false);

    state = wizardBack(state);
    expect(state.step).toBe('workflow');
    expect(state.templateId).toBe('wf-template-a');
    expect(state.idea).toContain('修表匠');
  });

  it('refuses to advance until a pipeline is selected', () => {
    const state = wizardContinue({ ...initialWizardState(), templateId: '' });
    expect(state.step).toBe('workflow');
    expect(state.error).toBe('请先选择一套创作流水线。');
  });

  it('orders all three official pipelines before custom templates and hides one-time drafts', () => {
    const list = selectableTemplates([
      workflow({ id: 'wf-b', name: 'B 模板' }),
      workflow({ id: officialDeepWorkflowId, name: '精细' }),
      workflow({ id: 'wf-once-draft', name: '本书配置', is_template: false }),
      workflow({ id: defaultWorkflowId, name: '平衡' }),
      workflow({ id: officialFastWorkflowId, name: '极速' }),
      workflow({ id: 'wf-a', name: 'A 模板' }),
    ]);
    expect(list.map((item) => item.id)).toEqual([
      officialFastWorkflowId,
      defaultWorkflowId,
      officialDeepWorkflowId,
      'wf-a',
      'wf-b',
    ]);
    expect(templateSummaryLine(workflow({ quality_mode: 'fast' }))).toBe('极速模式 · V4 Flash 全阶段 · 1 个阶段');
    expect(templateSummaryLine(workflow({
      id: defaultWorkflowId,
      quality_mode: 'balanced',
      nodes: [
        stage('deepseek-v4-pro'),
        {
          ...stage('deepseek-v4-flash'),
          id: 'cover',
          type: 'cover',
        },
      ],
    }))).toBe('平衡模式 · V4 Pro 核心创作 · Flash 封面简报 · 2 个阶段');
  });
});
