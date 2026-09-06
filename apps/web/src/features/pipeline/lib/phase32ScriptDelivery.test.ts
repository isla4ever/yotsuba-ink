import { describe, expect, it } from "vitest"
import {
  buildScriptDeliveryManifest,
  parseScriptDeliveryArtifact,
  parseScriptDeliveryEnvelope,
  verifyScriptDeliveryBinding,
} from "./phase32ScriptDelivery"

const digest = "a".repeat(64)
const versionRef = `p32-script-committed-${"b".repeat(64)}`

describe("phase32ScriptDelivery", () => {
  it("parses a frozen delivery and builds its ordered Scene manifest", () => {
    const artifact = parseScriptDeliveryArtifact({
      title: "失序档案",
      author: "四叶墨",
      version_note: "锁定版",
      formats: ["fountain"],
      scene_refs: ["scene-1"],
      scene_version_refs: [versionRef],
    })
    const envelope = parseScriptDeliveryEnvelope(
      {
        run_id: "run-1",
        artifact_type: "script_delivery",
        dependency_status: "ready",
        deferred_reason: "",
        source_artifact_refs: ["p32-export-committed-ref", versionRef],
        artifact_ref: "p32-export-committed-ref",
        artifact_digest: digest,
        items: [receipt()],
      },
      "run-1",
    )
    expect(envelope.dependencyStatus).toBe("ready")
    expect(envelope.artifactType).toBe("script_delivery")
    expect(envelope.sourceArtifactRefs).toEqual([
      "p32-export-committed-ref",
      versionRef,
    ])

    expect(
      verifyScriptDeliveryBinding(
        artifact,
        envelope,
        "p32-export-committed-ref",
        digest,
      ),
    ).toBe("")
    expect(
      buildScriptDeliveryManifest(artifact, {
        "scene-1": {
          scene_ref: "scene-1",
          blocks: [
            { kind: "scene_heading", text: "内景 档案室 - 夜" },
            { kind: "action", text: "林墨雨摊开签名页。" },
            {
              kind: "dialogue",
              text: "写进公开记录。",
              speaker_ref: "lin-moyu",
            },
          ],
        },
      }),
    ).toEqual([
      expect.objectContaining({
        ordinal: 1,
        sceneRef: "scene-1",
        heading: "内景 档案室 - 夜",
        blockCount: 3,
        actionBlocks: 1,
        dialogueBlocks: 1,
        valid: true,
      }),
    ])
  })

  it("rejects malformed refs and detects receipt metadata drift", () => {
    expect(() =>
      parseScriptDeliveryArtifact({
        title: "失序档案",
        author: "",
        version_note: "",
        formats: ["fountain"],
        scene_refs: ["scene-1"],
        scene_version_refs: ["candidate-version"],
      }),
    ).toThrow("格式或 Scene 版本绑定无效")

    const artifact = parseScriptDeliveryArtifact({
      title: "失序档案",
      author: "四叶墨",
      version_note: "锁定版",
      formats: ["fountain"],
      scene_refs: ["scene-1"],
      scene_version_refs: [versionRef],
    })
    const envelope = parseScriptDeliveryEnvelope(
      {
        run_id: "run-1",
        artifact_type: "script_delivery",
        dependency_status: "ready",
        deferred_reason: "",
        source_artifact_refs: ["p32-export-committed-ref", versionRef],
        artifact_ref: "p32-export-committed-ref",
        artifact_digest: digest,
        items: [{ ...receipt(), title: "漂移标题" }],
      },
      "run-1",
    )
    expect(
      verifyScriptDeliveryBinding(
        artifact,
        envelope,
        "p32-export-committed-ref",
        digest,
      ),
    ).toBe("交付文件元数据与冻结 Artifact 不一致")
  })

  it("rejects an envelope whose dependency metadata is missing or deferred", () => {
    expect(() =>
      parseScriptDeliveryEnvelope(
        {
          run_id: "run-1",
          artifact_ref: "p32-export-committed-ref",
          artifact_digest: digest,
          items: [receipt()],
        },
        "run-1",
      ),
    ).toThrow("交付依赖元数据与当前交付类型不一致")
    expect(() =>
      parseScriptDeliveryEnvelope(
        {
          run_id: "run-1",
          artifact_type: "script_delivery",
          dependency_status: "deferred",
          deferred_reason: "image_acceptance_not_in_current_wave",
          source_artifact_refs: [],
          artifact_ref: "p32-export-committed-ref",
          artifact_digest: digest,
          items: [receipt()],
        },
        "run-1",
      ),
    ).toThrow("交付依赖元数据与当前交付类型不一致")
  })
})

function receipt() {
  return {
    export_id: "script-export-1-fountain",
    run_id: "run-1",
    artifact_ref: "p32-export-committed-ref",
    artifact_digest: digest,
    format: "fountain",
    scene_refs: ["scene-1"],
    scene_version_refs: [versionRef],
    title: "失序档案",
    author: "四叶墨",
    version_note: "锁定版",
    filename: "失序档案.fountain",
    media_type: "text/plain; charset=utf-8",
    size_bytes: 128,
    sha256: "c".repeat(64),
    created_at: "2026-08-24T20:00:00Z",
  }
}
