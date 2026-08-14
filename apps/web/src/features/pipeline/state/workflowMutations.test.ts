import { describe, expect, it } from 'vitest';
import { updateStageInputDefault } from '../lib/stageConfig';
import { defaultWorkflow } from './defaultWorkflow';
import { withDeletedKnowledgeDocument } from './workflowMutations';

describe('withDeletedKnowledgeDocument', () => {
  it('removes only the deleted document from the persisted brief-stage input', () => {
    const workflow = {
      ...defaultWorkflow,
      nodes: defaultWorkflow.nodes.map((stage) => (
        stage.id === 'brief'
          ? updateStageInputDefault(stage, 'knowledge_base_doc_ids', ['doc-a', 'doc-b'])
          : stage
      )),
    };

    const next = withDeletedKnowledgeDocument(workflow, 'doc-a');
    const brief = next.nodes.find((stage) => stage.id === 'brief');
    const selectedDocuments = brief?.input_schema.find(
      (field) => field.key === 'knowledge_base_doc_ids',
    )?.default;

    expect(selectedDocuments).toEqual(['doc-b']);
    expect(next.quality_mode).toBe(workflow.quality_mode);
    expect(next.nodes.find((stage) => stage.id === 'spine')).toBe(
      workflow.nodes.find((stage) => stage.id === 'spine'),
    );
  });
});
