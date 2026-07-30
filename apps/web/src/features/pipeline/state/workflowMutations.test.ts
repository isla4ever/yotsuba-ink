import { describe, expect, it } from 'vitest';
import { updateStageInputDefault } from '../lib/stageConfig';
import { defaultWorkflow } from './defaultWorkflow';
import { withDeletedKnowledgeDocument } from './workflowMutations';

describe('withDeletedKnowledgeDocument', () => {
  it('removes only the deleted document from the persisted info-stage input', () => {
    const workflow = {
      ...defaultWorkflow,
      nodes: defaultWorkflow.nodes.map((stage) => (
        stage.id === 'info'
          ? updateStageInputDefault(stage, 'knowledge_base_doc_ids', ['doc-a', 'doc-b'])
          : stage
      )),
    };

    const next = withDeletedKnowledgeDocument(workflow, 'doc-a');
    const info = next.nodes.find((stage) => stage.id === 'info');
    const selectedDocuments = info?.input_schema.find(
      (field) => field.key === 'knowledge_base_doc_ids',
    )?.default;

    expect(selectedDocuments).toEqual(['doc-b']);
    expect(next.quality_mode).toBe(workflow.quality_mode);
    expect(next.nodes.find((stage) => stage.id === 'summary')).toBe(
      workflow.nodes.find((stage) => stage.id === 'summary'),
    );
  });
});
