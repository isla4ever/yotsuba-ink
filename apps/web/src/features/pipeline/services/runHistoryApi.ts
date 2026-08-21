import type {
  ExportReceipt,
  RunHistoryItem,
  RunHistoryResponse,
} from "../contracts/runHistory"
import { verifyExportBlob } from "../lib/exportIntegrity"
import { RunApiError } from "./runApi"

export async function listRunHistory(
  params: { limit?: number; projectId?: string; status?: string } = {},
  signal?: AbortSignal,
): Promise<RunHistoryResponse> {
  const query = new URLSearchParams()
  if (params.limit) query.set("limit", String(params.limit))
  if (params.projectId) query.set("project_id", params.projectId)
  if (params.status) query.set("status", params.status)
  const url = `/api/runs/history${query.size ? `?${query}` : ""}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const payload: unknown = await response.json()
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.items) ||
    typeof payload.next_cursor !== "string"
  ) {
    throw new RunApiError("Run 历史接口返回了无法识别的数据。", 502)
  }
  return {
    items: payload.items.map(parseRunHistoryItem),
    next_cursor: payload.next_cursor,
  }
}

export async function listRunExports(
  runId: string,
  signal?: AbortSignal,
): Promise<ExportReceipt[]> {
  const url = `/api/runs/${encodeURIComponent(runId)}/exports`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const payload: unknown = await response.json()
  if (!isRecord(payload) || !Array.isArray(payload.items))
    throw new RunApiError("导出列表接口返回了无法识别的数据。", 502)
  return payload.items.map(parseExportReceipt)
}

export function exportDownloadUrl(runId: string, exportId: string) {
  return `/api/runs/${encodeURIComponent(runId)}/exports/${encodeURIComponent(exportId)}`
}

export async function downloadRunExportReceipt(
  runId: string,
  exportId: string,
  options: {
    expectedSha256?: string
    expectedSizeBytes?: number
    signal?: AbortSignal
  } = {},
): Promise<{ blob: Blob; filename: string }> {
  const url = exportDownloadUrl(runId, exportId)
  const response = await fetch(url, { signal: options.signal })
  if (!response.ok) throw await responseError(response, url)
  const disposition = response.headers.get("content-disposition") ?? ""
  const blob = await response.blob()
  await verifyExportBlob(blob, {
    expectedSha256: options.expectedSha256,
    expectedSizeBytes: options.expectedSizeBytes,
    requireResponseSha256: true,
    responseSha256: response.headers.get("x-export-sha256") ?? "",
  })
  return { blob, filename: filenameFromDisposition(disposition) }
}

function parseRunHistoryItem(value: unknown): RunHistoryItem {
  if (!isRecord(value) || !isRecord(value.current_stage)) throw invalidHistory()
  const status = value.status
  if (
    ![
      "created",
      "running",
      "awaiting_decision",
      "failed",
      "completed",
      "cancelled",
    ].includes(String(status))
  )
    throw invalidHistory()
  if (!["fast", "balanced", "deep"].includes(String(value.quality_mode)))
    throw invalidHistory()
  if (
    !requiredStrings(value, [
      "run_id",
      "project_id",
      "title",
      "created_at",
      "updated_at",
      "completed_at",
      "summary",
      "checkpoint_id",
    ])
  )
    throw invalidHistory()
  if (!requiredStrings(value.current_stage, ["id", "label", "type"]))
    throw invalidHistory()
  if (
    !Array.isArray(value.completed_stage_ids) ||
    !value.completed_stage_ids.every((item) => typeof item === "string")
  )
    throw invalidHistory()
  if (!requiredNumbers(value, ["words", "total_tokens", "export_count"]))
    throw invalidHistory()
  if (
    typeof value.can_branch !== "boolean" ||
    typeof value.export_ready !== "boolean"
  )
    throw invalidHistory()
  if (
    value.estimated_cost_usd !== null &&
    typeof value.estimated_cost_usd !== "number"
  )
    throw invalidHistory()
  const latestExport =
    value.latest_export === null
      ? null
      : parseExportReceipt(value.latest_export)
  return { ...value, latest_export: latestExport } as RunHistoryItem
}

function parseExportReceipt(value: unknown): ExportReceipt {
  if (!isRecord(value) || !isRecord(value.metadata))
    throw new RunApiError("导出 Receipt 不符合当前合同。", 502)
  if (
    !requiredStrings(value, [
      "export_id",
      "run_id",
      "artifact_id",
      "artifact_signature",
      "cover_asset_id",
      "filename",
      "media_type",
      "sha256",
      "created_at",
    ])
  )
    throw new RunApiError("导出 Receipt 不符合当前合同。", 502)
  if (!requiredStrings(value.metadata, ["title", "author", "version_note"]))
    throw new RunApiError("导出元数据不符合当前合同。", 502)
  if (
    !["md", "json", "zip"].includes(String(value.format)) ||
    !Array.isArray(value.chapter_version_ids) ||
    typeof value.size_bytes !== "number"
  )
    throw new RunApiError("导出 Receipt 不符合当前合同。", 502)
  return value as ExportReceipt
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function requiredStrings(value: Record<string, unknown>, keys: string[]) {
  return keys.every((key) => typeof value[key] === "string")
}

function requiredNumbers(value: Record<string, unknown>, keys: string[]) {
  return keys.every(
    (key) => typeof value[key] === "number" && Number.isFinite(value[key]),
  )
}

function invalidHistory() {
  return new RunApiError("Run 历史条目不符合当前合同。", 502)
}

async function responseError(response: Response, url: string) {
  let detail = ""
  try {
    const payload = (await response.json()) as { detail?: unknown }
    detail = typeof payload.detail === "string" ? payload.detail : ""
  } catch {
    detail = ""
  }
  return new RunApiError(
    detail || `请求失败：${url} (${response.status})`,
    response.status,
  )
}

function filenameFromDisposition(value: string) {
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      throw new RunApiError("导出文件名不是有效的 UTF-8。", 502)
    }
  }
  const plain = value.match(/filename="?([^";]+)"?/i)?.[1]
  if (!plain) throw new RunApiError("导出响应缺少文件名。", 502)
  return plain
}
