import type { ProjectRecord, ProjectSummary } from "../contracts/project"
import type { CreationIntentDraft } from "../contracts/creationWizard"

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
  intent: CreationIntentDraft
  workflowId: string
  idempotencyKey: string
}): Promise<ProjectRecord> {
  const response = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      idempotency_key: input.idempotencyKey,
      selection: {
        intent: {
          creative_intent: input.intent.creativeIntent.trim(),
          creation_language: "zh-CN",
          creation_kind: input.intent.creationKind,
          novel_length_class: input.intent.novelLengthClass,
          requested_target: input.intent.requestedTarget,
        },
        mode: "existing",
        workflow_id: input.workflowId,
      },
    }),
  })
  if (!response.ok) throw await projectApiError(response, "/api/projects")
  return parseProject(await response.json(), "/api/projects")
}

export async function getProjectSummary(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectSummary> {
  const url = `/api/projects/${encodeURIComponent(projectId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await projectApiError(response, url)
  const project = parseProject(await response.json(), url)
  return {
    project,
    latest_run: null,
    title: project.title,
    status: project.run_status,
    current_stage: {
      id: project.active_stage.stage_id,
      label: project.active_stage.label,
      type: project.active_stage.stage_id,
    },
    completed_stage_ids: project.completed_stage_ids,
    words: project.words,
    updated_at: project.updated_at,
  }
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
    record.architecture_version !== "phase32-routes-v1" ||
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
    typeof record.latest_run_id !== "string" ||
    !record.latest_run_id ||
    !isCreationRouteId(record.creation_route_id) ||
    typeof record.route_revision !== "string" ||
    typeof record.route_label !== "string" ||
    typeof record.deliverable_kind !== "string" ||
    typeof record.run_status !== "string" ||
    !isActiveStage(record.active_stage) ||
    !Array.isArray(record.stage_manifest) ||
    !record.stage_manifest.every(isStageManifest) ||
    !record.stage_status ||
    typeof record.stage_status !== "object" ||
    !Array.isArray(record.completed_stage_ids) ||
    !record.completed_stage_ids.every((item) => typeof item === "string") ||
    !record.progress ||
    typeof record.progress.completed !== "number" ||
    typeof record.progress.total !== "number" ||
    typeof record.progress.ratio !== "number" ||
    typeof record.target !== "number" ||
    (record.target_unit !== "minutes" && record.target_unit !== "characters") ||
    typeof record.words !== "number" ||
    !record.provider_usage ||
    typeof record.provider_usage !== "object" ||
    !Array.isArray(record.pending_decisions)
  )
    throw invalidProjectContract(url)
  return record as ProjectRecord
}

function isCreationRouteId(value: unknown) {
  return (
    value === "screenplay_sample" ||
    value === "short_novel" ||
    value === "long_novel"
  )
}

function isActiveStage(value: unknown) {
  if (!value || typeof value !== "object") return false
  const stage = value as Record<string, unknown>
  return (
    typeof stage.stage_id === "string" &&
    typeof stage.label === "string" &&
    typeof stage.ordinal === "number" &&
    typeof stage.total === "number"
  )
}

function isStageManifest(value: unknown) {
  if (!value || typeof value !== "object") return false
  const stage = value as Record<string, unknown>
  return (
    typeof stage.ordinal === "number" &&
    typeof stage.stage_id === "string" &&
    typeof stage.label === "string" &&
    typeof stage.artifact_kind === "string" &&
    typeof stage.workbench_kind === "string" &&
    (typeof stage.provider_task_kind === "string" ||
      stage.provider_task_kind === null) &&
    Array.isArray(stage.upstream_stage_ids) &&
    Array.isArray(stage.downstream_stage_ids) &&
    typeof stage.collaboration_enabled === "boolean"
  )
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
