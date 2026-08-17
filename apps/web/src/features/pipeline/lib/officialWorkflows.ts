export const officialFastWorkflowId = 'official-deepseek-fast';
export const officialBalancedWorkflowId = 'official-deepseek-balanced';
export const officialDeepWorkflowId = 'official-deepseek-deep';
export const defaultWorkflowId = officialBalancedWorkflowId;

export const officialWorkflowOrder = [
  officialFastWorkflowId,
  officialBalancedWorkflowId,
  officialDeepWorkflowId,
] as const;

export function isOfficialWorkflowId(workflowId: string): boolean {
  return (officialWorkflowOrder as readonly string[]).includes(workflowId);
}

export function isOneTimeWorkflowId(workflowId: string): boolean {
  return workflowId.startsWith('wf-once-');
}
