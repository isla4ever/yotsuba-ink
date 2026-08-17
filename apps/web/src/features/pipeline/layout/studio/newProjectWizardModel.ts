import type { WorkflowDefinition } from '../../contracts';
import {
  defaultWorkflowId,
  isOfficialWorkflowId,
  isOneTimeWorkflowId,
  officialBalancedWorkflowId,
  officialWorkflowOrder,
} from '../../lib/officialWorkflows';

/**
 * Pure state machine for the new-project wizard (Phase 11.2).
 *
 * Phase 12 B4: with at most one selectable template (the always-present
 * default) there is no real choice — `wizardContinue` called with the template
 * list lands directly on a submit-ready state so the wizard can create
 * immediately instead of showing the template step. Multi-template lists keep
 * the selection step.
 */

export type NewProjectWizardStep = 'workflow' | 'idea';

export type NewProjectWizardState = {
  step: NewProjectWizardStep;
  idea: string;
  templateId: string;
  error: string;
  submitting: boolean;
};

export function initialWizardState(): NewProjectWizardState {
  return { step: 'workflow', idea: '', templateId: defaultWorkflowId, error: '', submitting: false };
}

export function wizardWithIdea(state: NewProjectWizardState, idea: string): NewProjectWizardState {
  return { ...state, idea, error: '' };
}

/**
 * Step 1 → 2: the title is the only required field. When the selectable
 * template list is passed and offers no real choice, the sole (default)
 * template is auto-selected and the returned state is immediately
 * submittable — callers should create directly instead of rendering step 2.
 */
export function wizardContinue(state: NewProjectWizardState): NewProjectWizardState {
  if (state.step !== 'workflow') return state;
  if (!state.templateId) return { ...state, error: '请先选择一套创作流水线。' };
  return { ...state, step: 'idea', error: '' };
}

export function wizardBack(state: NewProjectWizardState): NewProjectWizardState {
  if (state.step !== 'idea') return state;
  return { ...state, step: 'workflow', error: '' };
}

export function wizardSelectTemplate(state: NewProjectWizardState, templateId: string): NewProjectWizardState {
  return { ...state, templateId, error: '' };
}

export function wizardCanSubmit(state: NewProjectWizardState): boolean {
  return state.step === 'idea' && Boolean(state.idea.trim()) && Boolean(state.templateId) && !state.submitting;
}

/** Templates offered by the wizard: the three official modes, then user templates. */
export function selectableTemplates(workflows: WorkflowDefinition[]): WorkflowDefinition[] {
  const templates = workflows.filter((item) => item.is_template && !isOneTimeWorkflowId(item.id));
  return [...templates].sort((left, right) => {
    const leftOfficial = officialWorkflowOrder.indexOf(left.id as typeof officialWorkflowOrder[number]);
    const rightOfficial = officialWorkflowOrder.indexOf(right.id as typeof officialWorkflowOrder[number]);
    if (leftOfficial >= 0 || rightOfficial >= 0) {
      if (leftOfficial < 0) return 1;
      if (rightOfficial < 0) return -1;
      return leftOfficial - rightOfficial;
    }
    return left.name.localeCompare(right.name, 'zh-CN');
  });
}

export { defaultWorkflowId as defaultTemplateId, isOfficialWorkflowId as isOfficialTemplateId };

export const templateQualityLabels: Record<string, string> = {
  fast: '极速模式',
  balanced: '平衡模式',
  deep: '精细模式',
};

export function templateSummaryLine(workflow: WorkflowDefinition): string {
  const mode = templateQualityLabels[workflow.quality_mode] ?? workflow.quality_mode;
  return `${mode} · ${templateModelStrategy(workflow)} · ${workflow.nodes.length} 个阶段`;
}

export function templateModelStrategy(workflow: WorkflowDefinition): string {
  const models = new Set(
    workflow.nodes
      .filter((stage) => stage.type !== 'export')
      .map((stage) => stage.model_settings.model),
  );
  if (models.size === 1 && models.has('deepseek-v4-flash')) return 'V4 Flash 全阶段';
  if (models.size === 1 && models.has('deepseek-v4-pro')) return 'V4 Pro 全阶段';
  if (
    workflow.id === officialBalancedWorkflowId
    && models.has('deepseek-v4-flash')
    && models.has('deepseek-v4-pro')
  ) return 'V4 Pro 核心创作 · Flash 封面简报';
  if (models.has('deepseek-v4-flash') && models.has('deepseek-v4-pro')) return 'V4 Pro + Flash 分阶段';
  return '自定义模型分配';
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
    if (stage.type === 'export') {
      return {
        id: stage.id,
        label: stage.label,
        model: '系统确定性导出',
        provider: 'Yotsuba Ink',
      };
    }
    const profile = providers.get(stage.provider_profile_id);
    return {
      id: stage.id,
      label: stage.label,
      model: stage.model_settings.model || profile?.default_model || '未指定模型',
      provider: profile?.name || '未绑定服务',
    };
  });
}
