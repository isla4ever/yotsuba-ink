import type {
  CoverAssetCollection,
  CoverAssetRecord,
} from "../contracts/coverAsset"
import { RunApiError } from "./runApi"

export async function getCoverAssets(
  runId: string,
  signal?: AbortSignal,
): Promise<CoverAssetCollection> {
  const url = `/api/runs/${encodeURIComponent(runId)}/cover-assets`
  const response = await fetch(url, { signal })
  if (!response.ok)
    throw new RunApiError(`封面资产读取失败：${runId}`, response.status)
  const payload: unknown = await response.json()
  if (
    !isRecord(payload) ||
    payload.run_id !== runId ||
    !Number.isInteger(payload.generation_attempt) ||
    !Array.isArray(payload.items)
  ) {
    throw new RunApiError("封面资产接口返回了无法识别的数据。", 502)
  }
  return {
    run_id: runId,
    generation_attempt: payload.generation_attempt as number,
    items: payload.items.map(parseCoverAsset),
  }
}

export function coverAssetContentUrl(runId: string, asset: CoverAssetRecord) {
  return (
    asset.content_url ||
    `/api/runs/${encodeURIComponent(runId)}/cover-assets/${encodeURIComponent(asset.asset_id)}`
  )
}

function parseCoverAsset(value: unknown): CoverAssetRecord {
  if (!isRecord(value)) throw invalidAsset()
  const strings = [
    "asset_id",
    "run_id",
    "operation_key",
    "sha256",
    "mime_type",
    "extension",
    "provider_asset_id",
    "revised_prompt",
    "created_at",
    "content_url",
  ]
  const numbers = [
    "candidate_index",
    "generation_attempt",
    "width",
    "height",
    "size_bytes",
  ]
  if (
    strings.some((key) => typeof value[key] !== "string") ||
    numbers.some(
      (key) => typeof value[key] !== "number" || !Number.isFinite(value[key]),
    ) ||
    !/^[a-f0-9]{64}$/i.test(String(value.sha256))
  ) {
    throw invalidAsset()
  }
  return value as CoverAssetRecord
}

function invalidAsset() {
  return new RunApiError("封面资产记录不符合当前合同。", 502)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}
