import type {
  ArtifactPatchCandidate,
  CollaborationContextPreviewInput,
  CollaborationContextReceipt,
  CollaborationSettings,
  CollaborationSettingsEnvelope,
  CollaborationThread,
  CollaborationThreadDetail,
  CollaborationTurn,
  CreateCollaborationThreadInput,
} from "../contracts/authorCollaboration"

export class AuthorCollaborationApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
    readonly detail: Record<string, unknown> = {},
  ) {
    super(message)
  }
}

export async function listCollaborationThreads(
  runId: string,
  signal?: AbortSignal,
): Promise<CollaborationThread[]> {
  const payload = await requestJson<{ threads: CollaborationThread[] }>(
    endpoint(runId, "/threads"),
    { signal },
  )
  return payload.threads
}

export function createCollaborationThread(
  runId: string,
  input: CreateCollaborationThreadInput,
): Promise<CollaborationThread> {
  return requestJson(endpoint(runId, "/threads"), jsonInit("POST", input))
}

export function getCollaborationThread(
  runId: string,
  threadId: string,
  signal?: AbortSignal,
): Promise<CollaborationThreadDetail> {
  return requestJson(
    endpoint(runId, `/threads/${encodeURIComponent(threadId)}`),
    { signal },
  )
}

export function updateCollaborationThread(
  runId: string,
  threadId: string,
  input: {
    title?: string
    status?: "active" | "archived"
  },
): Promise<CollaborationThread> {
  return requestJson(
    endpoint(runId, `/threads/${encodeURIComponent(threadId)}`),
    jsonInit("PATCH", input),
  )
}

export function deleteCollaborationThread(
  runId: string,
  threadId: string,
): Promise<CollaborationThread> {
  return requestJson(
    endpoint(runId, `/threads/${encodeURIComponent(threadId)}`),
    { method: "DELETE" },
  )
}

export function previewCollaborationContext(
  runId: string,
  threadId: string,
  input: CollaborationContextPreviewInput,
): Promise<CollaborationContextReceipt> {
  return requestJson(
    endpoint(runId, `/threads/${encodeURIComponent(threadId)}/context-preview`),
    jsonInit("POST", input),
  )
}

export function createCollaborationTurn(
  runId: string,
  threadId: string,
  input: CollaborationContextPreviewInput & { preview_signature: string },
): Promise<CollaborationTurn> {
  return requestJson(
    endpoint(runId, `/threads/${encodeURIComponent(threadId)}/turns`),
    jsonInit("POST", input),
  )
}

export function cancelCollaborationTurn(
  runId: string,
  threadId: string,
  turnId: string,
): Promise<CollaborationTurn> {
  return requestJson(
    endpoint(
      runId,
      `/threads/${encodeURIComponent(threadId)}/turns/${encodeURIComponent(turnId)}/cancel`,
    ),
    { method: "POST" },
  )
}

export function rejectCollaborationPatch(
  runId: string,
  patchId: string,
): Promise<ArtifactPatchCandidate> {
  return requestJson(
    endpoint(runId, `/patches/${encodeURIComponent(patchId)}/reject`),
    { method: "POST" },
  )
}

export function getCollaborationSettings(
  signal?: AbortSignal,
): Promise<CollaborationSettingsEnvelope> {
  return requestJson("/api/collaboration/settings", { signal })
}

export function saveCollaborationSettings(
  settings: CollaborationSettings,
): Promise<CollaborationSettingsEnvelope> {
  return requestJson("/api/collaboration/settings", jsonInit("PUT", settings))
}

function endpoint(runId: string, suffix: string) {
  return `/api/runs/${encodeURIComponent(runId)}/collaboration${suffix}`
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail: Record<string, unknown> = {}
    try {
      const payload = (await response.json()) as { detail?: unknown }
      detail =
        payload.detail &&
        typeof payload.detail === "object" &&
        !Array.isArray(payload.detail)
          ? payload.detail as Record<string, unknown>
          : {}
    } catch {
      // The stable status remains useful when an upstream proxy returns HTML.
    }
    throw new AuthorCollaborationApiError(
      typeof detail.message === "string"
        ? detail.message
        : `作者协作请求失败 (${response.status})`,
      typeof detail.code === "string" ? detail.code : "request_failed",
      response.status,
      detail,
    )
  }
  return response.json() as Promise<T>
}
