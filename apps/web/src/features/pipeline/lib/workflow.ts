import type { CanvasLayout, QualityMode, WorkflowDefinition, WorkflowStage } from '../contracts';

export function updateStage(workflow: WorkflowDefinition, stage: WorkflowStage): WorkflowDefinition {
  const nodes = workflow.nodes.map((item) => (item.id === stage.id ? stage : item));
  return { ...workflow, nodes };
}

export function updateCanvasLayout(workflow: WorkflowDefinition, canvas_layout: CanvasLayout): WorkflowDefinition {
  return { ...workflow, canvas_layout };
}

export function stageInputDefaults(stage: WorkflowStage) {
  return Object.fromEntries(stage.input_schema.map((field) => [field.key, field.default ?? '']));
}

export function formatResult(value: unknown) {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

export function applyQualityMode(workflow: WorkflowDefinition, mode: QualityMode): WorkflowDefinition {
  return {
    ...workflow,
    quality_mode: mode,
    nodes: workflow.nodes.map((stage) => applyModeToStage(stage, mode)),
  };
}

function applyModeToStage(stage: WorkflowStage, mode: QualityMode): WorkflowStage {
  if (mode === 'fast') {
    return {
      ...stage,
      variant_policy: { ...stage.variant_policy, enabled: false, candidate_count: 1, retry_on_fail: false },
      input_schema: updateVersionFields(stage, false, 1),
    };
  }
  if (mode === 'balanced') {
    const configured = stage.input_schema.find((field) => field.key === 'enable_version_compare')?.default;
    const enabled = stage.type === 'chapter_text' && configured === true;
    const configuredCount = Number(stage.input_schema.find((field) => field.key === 'version_candidate_count')?.default);
    const candidateCount = Math.max(2, Math.min(3, Number.isFinite(configuredCount) ? configuredCount : stage.variant_policy.candidate_count || 2));
    return {
      ...stage,
      variant_policy: { ...stage.variant_policy, enabled, candidate_count: enabled ? candidateCount : 1, retry_on_fail: enabled },
      input_schema: stage.type === 'chapter_text' ? updateVersionFields(stage, enabled, candidateCount) : stage.input_schema,
    };
  }
  return {
    ...stage,
    variant_policy: { ...stage.variant_policy, enabled: false, candidate_count: 1, retry_on_fail: false },
    input_schema: stage.type === 'chapter_text' ? updateVersionFields(stage, false, 1) : stage.input_schema,
  };
}

function updateVersionFields(stage: WorkflowStage, enabled: boolean, count: number) {
  return stage.input_schema.map((field) => {
    if (field.key === 'enable_version_compare') return { ...field, default: enabled };
    if (field.key === 'version_candidate_count') return { ...field, default: count };
    return field;
  });
}
