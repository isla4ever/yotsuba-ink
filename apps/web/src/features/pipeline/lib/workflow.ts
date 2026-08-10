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
      input_schema: stage.input_schema,
    };
  }
  return stage;
}
