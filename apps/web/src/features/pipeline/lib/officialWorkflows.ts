export const officialWorkflowOrder = [
  "official-deepseek-fast",
  "official-deepseek-balanced",
  "official-deepseek-deep",
] as const

export function isOfficialWorkflowId(workflowId: string) {
  return (officialWorkflowOrder as readonly string[]).includes(workflowId)
}
