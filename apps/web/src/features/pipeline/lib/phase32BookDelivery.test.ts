import { describe, expect, it } from "vitest"
import {
  parseBookDeliveryArtifact,
  parseBookDeliveryEnvelope,
  verifyBookDeliveryBinding,
} from "./phase32BookDelivery"

describe("phase32BookDelivery", () => {
  it("parses one immutable receipt manifest without chapter fetches", () => {
    const artifact = parseBookDeliveryArtifact(artifactPayload())
    const envelope = parseBookDeliveryEnvelope(envelopePayload(), "run-book-1")

    expect(envelope.artifactType).toBe("book_delivery")
    expect(envelope.dependencyStatus).toBe("ready")
    expect(envelope.sourceArtifactRefs).toEqual([
      "p32-export-committed-ref",
      version("b"),
      version("c"),
    ])
    expect(envelope.receipts[0].chapter_manifest).toEqual([
      expect.objectContaining({
        ordinal: 1,
        chapter_ref: "section-1",
        title: "失踪页",
        character_count: 1280,
      }),
      expect.objectContaining({
        ordinal: 2,
        chapter_ref: "section-2",
        title: "公开记录",
        character_count: 1630,
      }),
    ])
    expect(
      verifyBookDeliveryBinding(
        artifact,
        envelope,
        "p32-export-committed-ref",
        "a".repeat(64),
      ),
    ).toBe("")
  })

  it("rejects manifest order drift before rendering", () => {
    const payload = envelopePayload()
    const item = payload.items[0]
    item.chapter_manifest = [...item.chapter_manifest].reverse()

    expect(() => parseBookDeliveryEnvelope(payload, "run-book-1")).toThrow(
      "正文清单与冻结顺序不一致",
    )
  })
})

function artifactPayload() {
  return {
    title: "被删去的城市",
    author: "四叶墨",
    version_note: "锁定交付版",
    formats: ["epub"],
    chapter_refs: ["section-1", "section-2"],
    chapter_version_refs: [version("b"), version("c")],
    volume_refs: [],
    cover_asset_ref: "asset-cover-1",
  }
}

function envelopePayload() {
  return {
    run_id: "run-book-1",
    artifact_type: "book_delivery",
    dependency_status: "ready",
    deferred_reason: "",
    source_artifact_refs: [
      "p32-export-committed-ref",
      version("b"),
      version("c"),
    ],
    artifact_ref: "p32-export-committed-ref",
    artifact_digest: "a".repeat(64),
    items: [
      {
        export_id: "book-export-1-epub",
        run_id: "run-book-1",
        creation_route_id: "short_novel",
        artifact_ref: "p32-export-committed-ref",
        artifact_digest: "a".repeat(64),
        format: "epub",
        chapter_refs: ["section-1", "section-2"],
        chapter_version_refs: [version("b"), version("c")],
        chapter_manifest: [
          {
            ordinal: 1,
            chapter_ref: "section-1",
            version_ref: version("b"),
            title: "失踪页",
            unit_kind: "chapter",
            volume_ref: "",
            character_count: 1280,
          },
          {
            ordinal: 2,
            chapter_ref: "section-2",
            version_ref: version("c"),
            title: "公开记录",
            unit_kind: "chapter",
            volume_ref: "",
            character_count: 1630,
          },
        ],
        volume_refs: [],
        cover_asset_ref: "asset-cover-1",
        cover_sha256: "d".repeat(64),
        title: "被删去的城市",
        author: "四叶墨",
        version_note: "锁定交付版",
        filename: "被删去的城市.epub",
        media_type: "application/epub+zip",
        size_bytes: 4096,
        sha256: "e".repeat(64),
        created_at: "2026-08-24T12:00:00Z",
      },
    ],
  }
}

function version(character: string) {
  return `p32-text-committed-${character.repeat(64)}`
}
