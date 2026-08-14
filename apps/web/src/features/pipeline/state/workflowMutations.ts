import type { CanvasLayout, WorkflowDefinition, WorkflowStage } from '../contracts';
import { updateStageInputDefault } from '../lib/stageConfig';
import { applyQualityMode, updateCanvasLayout, updateStage } from '../lib/workflow';

export function withUpdatedStage(workflow: WorkflowDefinition, stage: WorkflowStage) {
  return updateStage(workflow, stage);
}

export function withUpdatedCanvasLayout(workflow: WorkflowDefinition, layout: CanvasLayout) {
  return updateCanvasLayout(workflow, layout);
}

export function withAddedModelOption(workflow: WorkflowDefinition, providerId: string, model: string) {
  return {
    ...workflow,
    provider_profiles: workflow.provider_profiles.map((provider) => (
      provider.id === providerId
        ? { ...provider, model_options: Array.from(new Set([...(provider.model_options ?? []), model])) }
        : provider
    )),
  };
}

export function withDeletedKnowledgeDocument(workflow: WorkflowDefinition, docId: string) {
  return {
    ...workflow,
    nodes: workflow.nodes.map((stage) => {
      if (stage.id !== 'brief') return stage;
      const currentIds = stage.input_schema.find((field) => field.key === 'knowledge_base_doc_ids')?.default;
      const nextIds = Array.isArray(currentIds) ? currentIds.filter((item) => item !== docId) : [];
      return updateStageInputDefault(stage, 'knowledge_base_doc_ids', nextIds);
    }),
  };
}

export function withQualityMode(workflow: WorkflowDefinition, mode: WorkflowDefinition['quality_mode']) {
  return applyQualityMode(workflow, mode);
}
