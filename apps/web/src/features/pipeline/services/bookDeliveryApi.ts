import {
  parseBookDeliveryEnvelope,
  type BookDeliveryEnvelope,
  type BookDeliveryReceipt,
} from "../lib/phase32BookDelivery"
import { readPhase32DeliveryErrorDetails } from "../lib/phase32Delivery"
import type {
  Phase32DeliveryArtifactType,
  Phase32DeliveryDependencyStatus,
} from "../contracts/phase32Delivery"

export class BookDeliveryApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    details: Partial<{
      code: string
      artifactType: Phase32DeliveryArtifactType | ""
      dependencyStatus: Phase32DeliveryDependencyStatus | ""
      deferredReason: string
      sourceArtifactRefs: string[]
    }> = {},
  ) {
    super(message)
    this.name = "BookDeliveryApiError"
    this.code = details.code ?? ""
    this.artifactType = details.artifactType ?? ""
    this.dependencyStatus = details.dependencyStatus ?? ""
    this.deferredReason = details.deferredReason ?? ""
    this.sourceArtifactRefs = details.sourceArtifactRefs ?? []
  }

  readonly code: string
  readonly artifactType: Phase32DeliveryArtifactType | ""
  readonly dependencyStatus: Phase32DeliveryDependencyStatus | ""
  readonly deferredReason: string
  readonly sourceArtifactRefs: string[]
}

export async function getBookDelivery(
  runId: string,
  signal?: AbortSignal,
): Promise<BookDeliveryEnvelope> {
  const url = `/api/runs/${encodeURIComponent(runId)}/exports`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  return parseBookDeliveryEnvelope(await response.json(), runId)
}

export async function downloadBookDelivery(
  runId: string,
  receipt: BookDeliveryReceipt,
) {
  const url = `/api/runs/${encodeURIComponent(runId)}/exports/${encodeURIComponent(receipt.export_id)}`
  const response = await fetch(url)
  if (!response.ok) throw await responseError(response, url)
  const bytes = await response.arrayBuffer()
  const responseDigest = response.headers.get("x-content-sha256") ?? ""
  if (responseDigest && responseDigest !== receipt.sha256)
    throw new BookDeliveryApiError("下载响应与冻结文件哈希不一致", 502)
  const computedDigest = await sha256(bytes)
  if (computedDigest && computedDigest !== receipt.sha256)
    throw new BookDeliveryApiError("下载文件未通过 SHA-256 完整性校验", 502)

  const blob = new Blob([bytes], { type: receipt.media_type })
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = receipt.filename
  anchor.hidden = true
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}

async function sha256(bytes: ArrayBuffer) {
  if (!globalThis.crypto?.subtle) return ""
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes)
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")
}

async function responseError(response: Response, url: string) {
  let message = `小说交付请求失败：${url}`
  let details = readPhase32DeliveryErrorDetails(null)
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === "string") message = payload.detail
    else if (payload.detail && typeof payload.detail === "object") {
      details = readPhase32DeliveryErrorDetails(payload.detail)
      if ("message" in payload.detail)
        message = String((payload.detail as { message: unknown }).message)
    }
  } catch {
    // Keep the stable fallback for non-JSON responses.
  }
  return new BookDeliveryApiError(message, response.status, details)
}
