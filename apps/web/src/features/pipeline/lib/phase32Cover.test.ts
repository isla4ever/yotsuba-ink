import { describe, expect, it } from "vitest"
import type { CoverAssetRecord } from "../contracts/coverAsset"
import {
  parsePhase32Cover,
  phase32CoverAssetError,
  selectedPhase32CoverAsset,
} from "./phase32Cover"

describe("phase32Cover", () => {
  it("parses a real-asset proposal and resolves the formal selection", () => {
    const parsed = parsePhase32Cover(coverPayload())
    const assets = [asset("asset-cover-1"), asset("asset-cover-2")]

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.candidates).toHaveLength(2)
    expect(phase32CoverAssetError(parsed.artifact, assets)).toBe("")
    expect(selectedPhase32CoverAsset(parsed.artifact, assets)?.asset_id).toBe(
      "asset-cover-1",
    )
  })

  it("rejects a selection outside the proposal and reports missing bytes", () => {
    const invalid = parsePhase32Cover({
      ...coverPayload(),
      selected_asset_ref: "asset-cover-missing",
    })
    const parsed = parsePhase32Cover(coverPayload())

    expect(invalid.error).toContain("必须来自当前候选")
    expect(
      phase32CoverAssetError(parsed.artifact, [asset("asset-cover-1")]),
    ).toContain("尚未完成持久化核验")
  })

  it("accepts a CoverBrief-only artifact while image acceptance is deferred", () => {
    const parsed = parsePhase32Cover({
      brief: coverPayload().brief,
      candidates: [],
      selected_asset_ref: null,
      image_acceptance_status: "image_deferred",
    })

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.image_acceptance_status).toBe("image_deferred")
    expect(parsed.artifact?.candidates).toEqual([])
    expect(phase32CoverAssetError(parsed.artifact, [])).toBe("")
  })
})

function coverPayload() {
  return {
    brief: {
      concept: "冷色档案与一束被撕开的光",
      image_prompt: "现代城市档案室，竖版封面构图",
      palette: ["深靛蓝", "银灰"],
      negative_constraints: ["不要人物正脸"],
    },
    candidates: [
      {
        asset_ref: "asset-cover-1",
        alt_text: "档案室中的单束顶光",
        visual_notes: "主体留出标题安全区",
      },
      {
        asset_ref: "asset-cover-2",
        alt_text: "被撕开的城市档案",
        visual_notes: "强调纸张与城市的重叠",
      },
    ],
    selected_asset_ref: "asset-cover-1",
  }
}

function asset(assetId: string): CoverAssetRecord {
  return {
    asset_id: assetId,
    run_id: "run-cover-1",
    operation_key: `run-cover-1:cover:${assetId}`,
    candidate_index: 1,
    generation_attempt: 1,
    sha256: "a".repeat(64),
    mime_type: "image/png",
    extension: "png",
    width: 1024,
    height: 1536,
    size_bytes: 2048,
    provider_asset_id: assetId,
    revised_prompt: "",
    created_at: "2026-08-24T12:00:00Z",
    content_url: `/cover/${assetId}`,
  }
}
