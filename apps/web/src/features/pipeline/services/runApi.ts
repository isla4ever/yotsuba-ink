import type {
  ChapterVersionRecord,
  GraphRunEnvelope,
  RunArtifactRecord,
  StageArtifactDraftRecord,
} from "../contracts/run"

export class RunApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message)
    this.name = "RunApiError"
  }
}

export async function getRun(
  runId: string,
  signal?: AbortSignal,
): Promise<GraphRunEnvelope> {
  const url = `/api/runs/${encodeURIComponent(runId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  return parseRunEnvelope(await response.json(), url)
}

export async function getArtifactRecord(
  runId: string,
  artifactId: string,
  signal?: AbortSignal,
): Promise<RunArtifactRecord> {
  const url = `/api/runs/${encodeURIComponent(runId)}/artifact-records/${encodeURIComponent(artifactId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (!value || typeof value !== "object")
    throw new RunApiError(`Artifact 接口返回了无法识别的数据：${url}`, 502)
  return value as RunArtifactRecord
}

export async function getRunChapters(
  runId: string,
  signal?: AbortSignal,
): Promise<ChapterVersionRecord[]> {
  const url = `/api/runs/${encodeURIComponent(runId)}/chapters`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const payload = (await response.json()) as {
    run_id?: unknown
    chapters?: unknown
  }
  if (payload.run_id !== runId || !Array.isArray(payload.chapters)) {
    throw new RunApiError(`章节接口返回了无法识别的数据：${url}`, 502)
  }
  return payload.chapters as ChapterVersionRecord[]
}

export function streamExistingRun(
  runId: string,
  signal?: AbortSignal,
  after = 0,
) {
  return fetch(`/api/runs/${encodeURIComponent(runId)}/events?after=${after}`, {
    method: "GET",
    signal,
  })
}

export async function resolveRunDecision(
  runId: string,
  decisionId: string,
  action: "accept" | "regenerate" | "retry_evidence" | "cancel",
  domainRevision: number,
  artifact?: Record<string, unknown>,
  direction?: string,
) {
  const url = `/api/runs/${encodeURIComponent(runId)}/decisions/${encodeURIComponent(decisionId)}`
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      domain_revision: domainRevision,
      ...(artifact ? { artifact } : {}),
      ...(direction?.trim() ? { direction: direction.trim() } : {}),
    }),
  })
  if (!response.ok) throw await responseError(response, url)
}

export async function getStageArtifactDraft(
  runId: string,
  decisionId: string,
  signal?: AbortSignal,
): Promise<StageArtifactDraftRecord | null> {
  const url = `/api/runs/${encodeURIComponent(runId)}/stage-drafts/${encodeURIComponent(decisionId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  return response.json() as Promise<StageArtifactDraftRecord | null>
}

export async function saveStageArtifactDraft(
  runId: string,
  decisionId: string,
  domainRevision: number,
  sourceArtifactId: string,
  artifact: Record<string, unknown>,
): Promise<StageArtifactDraftRecord> {
  const url = `/api/runs/${encodeURIComponent(runId)}/stage-drafts/${encodeURIComponent(decisionId)}`
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_revision: domainRevision,
      source_artifact_id: sourceArtifactId,
      artifact,
    }),
  })
  if (!response.ok) throw await responseError(response, url)
  return response.json() as Promise<StageArtifactDraftRecord>
}

function parseRunEnvelope(value: unknown, url: string): GraphRunEnvelope {
  if (!value || typeof value !== "object") throw invalidRunContract(url)
  const envelope = value as Partial<GraphRunEnvelope>
  const definition = envelope.definition
  const readModel = envelope.read_model
  if (
    !definition ||
    definition.architecture_version !== "phase27-vnext" ||
    typeof definition.run_id !== "string" ||
    typeof definition.project_id !== "string" ||
    typeof definition.workflow_id !== "string" ||
    !isQualityMode(definition.quality_mode) ||
    !definition.provider_bindings ||
    typeof definition.provider_bindings !== "object" ||
    !validCoverBinding(definition.cover_asset_binding) ||
    !validExportPreferences(definition.export_preferences) ||
    !readModel ||
    typeof readModel.run_id !== "string" ||
    typeof readModel.project_id !== "string" ||
    typeof readModel.status !== "string" ||
    typeof readModel.active_stage_id !== "string" ||
    !readModel.stage_status ||
    typeof readModel.stage_status !== "object" ||
    !readModel.artifact_refs ||
    typeof readModel.artifact_refs !== "object" ||
    !Array.isArray(readModel.pending_decisions) ||
    typeof readModel.updated_at !== "string"
  )
    throw invalidRunContract(url)
  return envelope as GraphRunEnvelope
}

function isQualityMode(value: unknown) {
  return value === "fast" || value === "balanced" || value === "deep"
}

function validCoverBinding(value: unknown) {
  if (!value || typeof value !== "object") return false
  const binding = value as Record<string, unknown>
  return (
    typeof binding.provider_profile_id === "string" &&
    typeof binding.model === "string" &&
    Number.isInteger(binding.candidate_count) &&
    typeof binding.size === "string" &&
    ["low", "medium", "high"].includes(String(binding.quality)) &&
    typeof binding.timeout_seconds === "number" &&
    binding.failure_policy === "fail_run"
  )
}

function validExportPreferences(value: unknown) {
  if (!value || typeof value !== "object") return false
  const preferences = value as Record<string, unknown>
  return (
    ["md", "json", "zip"].includes(String(preferences.format)) &&
    typeof preferences.author === "string" &&
    typeof preferences.version_note === "string" &&
    typeof preferences.include_cover_image === "boolean"
  )
}

function invalidRunContract(url: string) {
  return new RunApiError(`Run 接口返回了无法识别的数据：${url}`, 502)
}

async function responseError(response: Response, url: string) {
  let detail = ""
  let code: string | undefined
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === "string") detail = payload.detail
    else if (payload.detail && typeof payload.detail === "object") {
      const structured = payload.detail as { code?: unknown; message?: unknown }
      code = typeof structured.code === "string" ? structured.code : undefined
      detail = typeof structured.message === "string" ? structured.message : ""
    }
  } catch {
    detail = ""
  }
  return new RunApiError(
    detail || `Run 请求失败：${url} (${response.status})`,
    response.status,
    code,
  )
}
