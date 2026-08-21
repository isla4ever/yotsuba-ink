import type { ProjectRecord, ProjectSummary } from "../contracts/project"

export class ProjectApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ProjectApiError"
  }
}

export async function listProjects(
  signal?: AbortSignal,
): Promise<ProjectRecord[]> {
  const response = await fetch("/api/projects", { signal })
  if (!response.ok) throw await projectApiError(response, "/api/projects")
  const payload: unknown = await response.json()
  if (!Array.isArray(payload)) throw invalidProjectContract("/api/projects")
  return payload.map((item) => parseProject(item, "/api/projects"))
}

export async function createProject(input: {
  idea: string
  templateWorkflowId?: string
  consumeWorkflowDraft?: boolean
}): Promise<ProjectRecord> {
  const response = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      idea: input.idea,
      ...(input.templateWorkflowId
        ? { template_workflow_id: input.templateWorkflowId }
        : {}),
      ...(input.consumeWorkflowDraft ? { consume_workflow_draft: true } : {}),
    }),
  })
  if (!response.ok) throw await projectApiError(response, "/api/projects")
  return parseProject(await response.json(), "/api/projects")
}

export async function getProjectSummary(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectSummary> {
  const url = `/api/projects/${encodeURIComponent(projectId)}/summary`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await projectApiError(response, url)
  const payload: unknown = await response.json()
  if (!payload || typeof payload !== "object") throw invalidProjectContract(url)
  const record = payload as Partial<ProjectSummary>
  if (
    typeof record.title !== "string" ||
    typeof record.status !== "string" ||
    !record.current_stage ||
    typeof record.current_stage !== "object" ||
    !Array.isArray(record.completed_stage_ids) ||
    !record.completed_stage_ids.every((item) => typeof item === "string") ||
    typeof record.words !== "number" ||
    !Number.isFinite(record.words) ||
    typeof record.updated_at !== "string"
  )
    throw invalidProjectContract(url)
  return {
    project: parseProject(record.project, url),
    latest_run: record.latest_run ?? null,
    title: record.title,
    status: record.status,
    current_stage: record.current_stage,
    completed_stage_ids: record.completed_stage_ids,
    words: record.words,
    updated_at: record.updated_at,
  }
}

export async function getProjectSummaries(
  projects: ProjectRecord[],
  signal?: AbortSignal,
  concurrency = 4,
): Promise<Record<string, ProjectSummary>> {
  const summaries: Record<string, ProjectSummary> = {}
  let nextIndex = 0
  const workers = Array.from(
    { length: Math.min(concurrency, projects.length) },
    async () => {
      while (nextIndex < projects.length) {
        const project = projects[nextIndex]
        nextIndex += 1
        try {
          summaries[project.id] = await getProjectSummary(project.id, signal)
        } catch (reason) {
          if (signal?.aborted) throw reason
        }
      }
    },
  )
  await Promise.all(workers)
  return summaries
}

export async function reorderProjects(
  projectIds: string[],
): Promise<ProjectRecord[]> {
  const response = await fetch("/api/projects/order", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_ids: projectIds }),
  })
  if (!response.ok) throw await projectApiError(response, "/api/projects/order")
  const payload: unknown = await response.json()
  if (!Array.isArray(payload))
    throw invalidProjectContract("/api/projects/order")
  return payload.map((item) => parseProject(item, "/api/projects/order"))
}

function parseProject(value: unknown, url: string): ProjectRecord {
  if (!value || typeof value !== "object") throw invalidProjectContract(url)
  const record = value as Partial<ProjectRecord>
  if (
    typeof record.id !== "string" ||
    !record.id ||
    typeof record.title !== "string" ||
    !record.title ||
    typeof record.summary !== "string" ||
    typeof record.accent_hue !== "number" ||
    record.accent_hue < 0 ||
    record.accent_hue > 360 ||
    typeof record.workflow_id !== "string" ||
    !record.workflow_id ||
    (record.status !== "active" && record.status !== "archived") ||
    typeof record.created_at !== "string" ||
    typeof record.updated_at !== "string" ||
    typeof record.latest_run_id !== "string"
  )
    throw invalidProjectContract(url)
  return record as ProjectRecord
}

function invalidProjectContract(url: string) {
  return new ProjectApiError(`Invalid Project API contract: ${url}`, 502)
}

async function projectApiError(response: Response, url: string) {
  let detail = ""
  try {
    const payload = (await response.json()) as { detail?: unknown }
    detail = typeof payload.detail === "string" ? payload.detail : ""
  } catch {
    detail = ""
  }
  return new ProjectApiError(
    detail || `Request failed: ${url} ${response.status}`,
    response.status,
  )
}
