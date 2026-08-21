import type { WorkflowDefinition } from "../contracts/workflow"

export class WorkflowApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "WorkflowApiError"
  }
}

export async function listWorkflowDefinitions(
  signal?: AbortSignal,
): Promise<WorkflowDefinition[]> {
  const response = await fetch("/api/workflows", { signal })
  if (!response.ok) throw await workflowApiError(response, "/api/workflows")
  const payload: unknown = await response.json()
  if (!Array.isArray(payload)) throw invalidWorkflowContract("/api/workflows")
  return payload.map((item) => parseWorkflow(item, "/api/workflows"))
}

export async function getWorkflowDefinition(
  workflowId: string,
  signal?: AbortSignal,
): Promise<WorkflowDefinition> {
  const url = `/api/workflows/${encodeURIComponent(workflowId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await workflowApiError(response, url)
  return parseWorkflow(await response.json(), url)
}

export async function duplicateWorkflowDefinition(
  workflowId: string,
  options: { new_id?: string; name?: string; is_template?: boolean } = {},
): Promise<WorkflowDefinition> {
  const url = `/api/workflows/${encodeURIComponent(workflowId)}/duplicate`
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  })
  if (!response.ok) throw await workflowApiError(response, url)
  return parseWorkflow(await response.json(), url)
}

export async function saveWorkflowDefinition(
  workflow: WorkflowDefinition,
): Promise<WorkflowDefinition> {
  const response = await fetch("/api/workflows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(workflow),
  })
  if (!response.ok) throw await workflowApiError(response, "/api/workflows")
  return parseWorkflow(await response.json(), "/api/workflows")
}

export async function deleteWorkflowDefinition(
  workflowId: string,
): Promise<void> {
  const url = `/api/workflows/${encodeURIComponent(workflowId)}`
  const response = await fetch(url, { method: "DELETE" })
  if (!response.ok) throw await workflowApiError(response, url)
}

function parseWorkflow(value: unknown, url: string): WorkflowDefinition {
  if (!value || typeof value !== "object") throw invalidWorkflowContract(url)
  const record = value as Partial<WorkflowDefinition>
  if (
    record.architecture_version !== "phase27-vnext" ||
    typeof record.id !== "string" ||
    !record.id ||
    typeof record.name !== "string" ||
    !record.name ||
    typeof record.version !== "string" ||
    typeof record.is_template !== "boolean" ||
    !isQualityMode(record.quality_mode) ||
    !Array.isArray(record.nodes) ||
    record.nodes.length !== 8 ||
    !record.nodes.every(isWorkflowStage) ||
    !Array.isArray(record.edges) ||
    !Array.isArray(record.provider_profiles)
  )
    throw invalidWorkflowContract(url)
  return record as WorkflowDefinition
}

function isWorkflowStage(
  value: unknown,
): value is WorkflowDefinition["nodes"][number] {
  if (!value || typeof value !== "object") return false
  const stage = value as Partial<WorkflowDefinition["nodes"][number]>
  return (
    typeof stage.id === "string" &&
    typeof stage.label === "string" &&
    typeof stage.provider_profile_id === "string" &&
    Boolean(stage.model_settings) &&
    typeof stage.model_settings?.model === "string" &&
    Array.isArray(stage.input_schema)
  )
}

function isQualityMode(
  value: unknown,
): value is WorkflowDefinition["quality_mode"] {
  return value === "fast" || value === "balanced" || value === "deep"
}

function invalidWorkflowContract(url: string) {
  return new WorkflowApiError(`工作流接口返回了无法识别的数据：${url}`, 502)
}

async function workflowApiError(response: Response, url: string) {
  let detail = ""
  try {
    const payload = (await response.json()) as { detail?: unknown }
    detail = typeof payload.detail === "string" ? payload.detail : ""
  } catch {
    detail = ""
  }
  return new WorkflowApiError(
    detail || `工作流请求失败：${url} (${response.status})`,
    response.status,
  )
}
