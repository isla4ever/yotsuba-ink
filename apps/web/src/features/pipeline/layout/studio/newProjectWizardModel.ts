import type { WorkflowDefinition } from '../../contracts';

/**
 * Pure state machine for the new-project wizard (Phase 11.2).
 *
 * Phase 12 B4: with at most one selectable template (the always-present
 * default) there is no real choice — `wizardContinue` called with the template
 * list lands directly on a submit-ready state so the wizard can create
 * immediately instead of showing the template step. Multi-template lists keep
 * the selection step.
 */

export const defaultTemplateId = 'default-novel-workflow';

export type NewProjectWizardStep = 'basics' | 'template';

export type NewProjectWizardState = {
  step: NewProjectWizardStep;
  title: string;
  summary: string;
  templateId: string;
  error: string;
  submitting: boolean;
};

export function initialWizardState(): NewProjectWizardState {
  return { step: 'basics', title: '', summary: '', templateId: defaultTemplateId, error: '', submitting: false };
}

export function wizardWithBasics(state: NewProjectWizardState, changes: Partial<Pick<NewProjectWizardState, 'title' | 'summary'>>): NewProjectWizardState {
  return { ...state, ...changes, error: '' };
}

/** B4: the template step only exists when there is more than one template to pick from. */
export function wizardNeedsTemplateStep(templates: readonly Pick<WorkflowDefinition, 'id'>[]): boolean {
  return templates.length > 1;
}

/**
 * Step 1 → 2: the title is the only required field. When the selectable
 * template list is passed and offers no real choice, the sole (default)
 * template is auto-selected and the returned state is immediately
 * submittable — callers should create directly instead of rendering step 2.
 */
export function wizardContinue(
  state: NewProjectWizardState,
  templates?: readonly Pick<WorkflowDefinition, 'id'>[],
): NewProjectWizardState {
  if (state.step !== 'basics') return state;
  if (!state.title.trim()) return { ...state, error: '请先填写书名。' };
  if (templates && !wizardNeedsTemplateStep(templates)) {
    return { ...state, step: 'template', templateId: templates[0]?.id ?? defaultTemplateId, error: '' };
  }
  return { ...state, step: 'template', error: '' };
}

export function wizardBack(state: NewProjectWizardState): NewProjectWizardState {
  if (state.step !== 'template') return state;
  return { ...state, step: 'basics', error: '' };
}

export function wizardSelectTemplate(state: NewProjectWizardState, templateId: string): NewProjectWizardState {
  return { ...state, templateId, error: '' };
}

export function wizardCanSubmit(state: NewProjectWizardState): boolean {
  return state.step === 'template' && Boolean(state.title.trim()) && Boolean(state.templateId) && !state.submitting;
}

/** Templates offered by the wizard: is_template flags plus the always-present default workflow. */
export function selectableTemplates(workflows: WorkflowDefinition[]): WorkflowDefinition[] {
  const templates = workflows.filter((item) => item.is_template || item.id === defaultTemplateId);
  return [...templates].sort((left, right) => {
    if (left.id === defaultTemplateId) return -1;
    if (right.id === defaultTemplateId) return 1;
    return left.name.localeCompare(right.name, 'zh-CN');
  });
}

export const templateQualityLabels: Record<string, string> = {
  fast: '快速档',
  balanced: '平衡档',
  deep: '精修档',
};

export function templateSummaryLine(workflow: WorkflowDefinition): string {
  const mode = templateQualityLabels[workflow.quality_mode] ?? workflow.quality_mode;
  return `${mode} · ${workflow.nodes.length} 个阶段`;
}

export type TemplateStageDigestRow = {
  id: string;
  label: string;
  model: string;
  provider: string;
};

/**
 * What a template actually commits a new book to: the stage chain plus the
 * model each stage will call. Without it the template list is unreadable.
 */
export function templateStageDigest(workflow: WorkflowDefinition): TemplateStageDigestRow[] {
  const providers = new Map(workflow.provider_profiles.map((profile) => [profile.id, profile]));
  return workflow.nodes.map((stage) => {
    const profile = providers.get(stage.provider_profile_id);
    return {
      id: stage.id,
      label: stage.label,
      model: stage.model_settings.model || profile?.default_model || '未指定模型',
      provider: profile?.name || '未绑定服务',
    };
  });
}
