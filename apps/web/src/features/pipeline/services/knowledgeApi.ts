import type {
  KnowledgeDeleteResponse,
  KnowledgeDocument,
  KnowledgeUploadPhase,
  KnowledgeUploadResponse,
} from "../contracts/knowledge"

export async function listKnowledgeDocuments(
  projectId: string,
  signal?: AbortSignal,
): Promise<KnowledgeDocument[]> {
  if (!projectId) throw new KnowledgeApiError("知识库请求缺少项目标识。", 422)
  const url = `/api/knowledge/documents?project_id=${encodeURIComponent(projectId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await knowledgeApiError(response, url)
  const payload: unknown = await response.json()
  if (!Array.isArray(payload))
    throw new KnowledgeApiError("知识库接口返回了无法识别的数据。", 502)
  return payload as KnowledgeDocument[]
}

export async function uploadKnowledgeFile(
  file: File,
  projectId: string,
  onPhase?: (phase: KnowledgeUploadPhase) => void,
): Promise<KnowledgeUploadResponse> {
  if (!projectId) throw new KnowledgeApiError("知识库上传缺少项目标识。", 422)
  onPhase?.("reading")
  const content = await fileToBase64(file)
  onPhase?.("indexing")
  const response = await fetch("/api/knowledge/documents/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: file.name.replace(/\.[^.]+$/, ""),
      content,
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      project_id: projectId,
      encoding: "base64",
    }),
  })
  if (!response.ok)
    throw await knowledgeApiError(response, "/api/knowledge/documents/upload")
  return response.json() as Promise<KnowledgeUploadResponse>
}

export async function deleteKnowledgeDocument(
  docId: string,
  projectId: string,
): Promise<KnowledgeDeleteResponse> {
  const url = `/api/knowledge/documents/${encodeURIComponent(docId)}?project_id=${encodeURIComponent(projectId)}`
  const response = await fetch(url, { method: "DELETE" })
  if (!response.ok) throw await knowledgeApiError(response, url)
  return response.json() as Promise<KnowledgeDeleteResponse>
}

export function knowledgeBackendLabel(documents: KnowledgeDocument[]) {
  const backends = new Set(
    documents.map((item) => item.backend).filter(Boolean),
  )
  if (!backends.size) return "等待资料"
  if (backends.size > 1) return "混合来源"
  const backend = [...backends][0]
  if (backend === "redis-hybrid") return "Redis Hybrid"
  if (backend === "redis-unavailable") return "Redis 待同步"
  return "本地 Hybrid"
}

class KnowledgeApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "KnowledgeApiError"
  }
}

async function knowledgeApiError(response: Response, url: string) {
  let detail = ""
  try {
    const payload = (await response.json()) as { detail?: unknown }
    detail = typeof payload.detail === "string" ? payload.detail : ""
  } catch {
    detail = ""
  }
  return new KnowledgeApiError(
    detail || `知识库请求失败：${url} (${response.status})`,
    response.status,
  )
}

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () =>
      resolve(String(reader.result || "").split(",")[1] || "")
    reader.readAsDataURL(file)
  })
}
