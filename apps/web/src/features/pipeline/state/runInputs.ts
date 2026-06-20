import type { RunInputs, WorkflowDefinition } from '../contracts';
import { stageInputDefaults } from '../lib/workflow';

export function buildRunInputs(workflow: WorkflowDefinition): RunInputs {
  return {
    title: '雾港旧声',
    theme: '悬疑、记忆、旧港、群像',
    quality_mode: workflow.quality_mode,
    stage_configs: Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stageInputDefaults(stage)])),
  };
}
