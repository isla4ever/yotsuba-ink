import type { WorkflowDefinition } from '../contracts';

export async function saveWorkflowDefinition(workflow: WorkflowDefinition) {
  const response = await fetch('/api/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(workflow),
  });
  if (!response.ok) throw new Error('保存工作流失败');
}
