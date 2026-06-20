import type { CanvasLayout, QualityMode, WorkflowDefinition, WorkflowStage } from '../types/workflow';

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
      quality_policy: { ...stage.quality_policy, retry_on_fail: false },
      input_schema: updateVersionFields(stage, false, 1),
    };
  }
  if (mode === 'balanced') {
    const enabled = stage.type === 'chapter_text' ? true : stage.variant_policy.enabled;
    return {
      ...stage,
      variant_policy: { ...stage.variant_policy, enabled, candidate_count: enabled ? 2 : 1, retry_on_fail: enabled },
      quality_policy: { ...stage.quality_policy, retry_on_fail: enabled || stage.quality_policy.retry_on_fail },
      input_schema: stage.type === 'chapter_text' ? updateVersionFields(stage, true, 2) : stage.input_schema,
    };
  }
  const textStage = ['summary', 'outline', 'detail_outline', 'chapter_text'].includes(stage.type);
  return {
    ...stage,
    variant_policy: { ...stage.variant_policy, enabled: textStage, candidate_count: textStage ? Math.max(3, stage.variant_policy.candidate_count) : 1, retry_on_fail: textStage },
    quality_policy: { ...stage.quality_policy, retry_on_fail: textStage || stage.quality_policy.retry_on_fail, min_score: textStage ? Math.max(stage.quality_policy.min_score, 0.84) : stage.quality_policy.min_score },
    input_schema: stage.type === 'chapter_text' ? updateVersionFields(stage, true, 3) : stage.input_schema,
  };
}

function updateVersionFields(stage: WorkflowStage, enabled: boolean, count: number) {
  return stage.input_schema.map((field) => {
    if (field.key === 'enable_version_compare') return { ...field, default: enabled };
    if (field.key === 'version_candidate_count') return { ...field, default: count };
    return field;
  });
}
