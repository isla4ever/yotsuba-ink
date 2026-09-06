// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import ScriptDeliveryStageView from "./ScriptDeliveryStageView"

const mocks = vi.hoisted(() => ({
  download: vi.fn(),
  reload: vi.fn(),
  setRoute: vi.fn(),
}))

vi.mock("../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: {
      architectureVersion: "phase32-routes-v1",
      creationRouteId: "screenplay_sample",
    },
    activeRun: {
      definition: { run_id: "run-delivery-1" },
      read_model: { updated_at: "2026-08-24T20:00:00Z" },
    },
    runError: "",
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../state/usePhase32ScriptDelivery", () => ({
  usePhase32ScriptDelivery: () => deliveryState(),
}))

vi.mock("../services/scriptDeliveryApi", () => ({
  downloadScriptDelivery: mocks.download,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("ScriptDeliveryStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.download.mockResolvedValue(undefined)
  })

  it("renders a read-only manifest and downloads the selected frozen file", async () => {
    const container = document.createElement("div")
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<ScriptDeliveryStageView />))

    expect(container.querySelectorAll("input, textarea, select")).toHaveLength(
      0,
    )
    expect(container.textContent).toContain("失序档案")
    expect(container.textContent).toContain("内景 档案室 - 夜")
    expect(container.textContent).toContain("1 committed")

    const download = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("下载 Fountain"),
    )!
    await act(async () => {
      download.click()
      await Promise.resolve()
    })
    expect(mocks.download).toHaveBeenCalledWith(
      "run-delivery-1",
      expect.objectContaining({ export_id: "script-export-1-fountain" }),
    )
    expect(container.textContent).toContain("已下载")

    const back = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("返回剧本正文"),
    )!
    act(() => back.click())
    expect(mocks.setRoute).toHaveBeenCalledWith("script")

    act(() => root.unmount())
    container.remove()
  })
})

function deliveryState() {
  const versionRef = `p32-script-committed-${"b".repeat(64)}`
  const receipt = {
    export_id: "script-export-1-fountain",
    run_id: "run-delivery-1",
    artifact_ref: "p32-export-committed-ref",
    artifact_digest: "a".repeat(64),
    format: "fountain" as const,
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
  return {
    artifact: {
      title: "失序档案",
      author: "四叶墨",
      version_note: "锁定版",
      formats: ["fountain"],
      scene_refs: ["scene-1"],
      scene_version_refs: [versionRef],
    },
    artifactDigest: "a".repeat(64),
    envelope: {
      runId: "run-delivery-1",
      artifactRef: "p32-export-committed-ref",
      artifactDigest: "a".repeat(64),
      artifactType: "script_delivery" as const,
      dependencyStatus: "ready" as const,
      deferredReason: "",
      sourceArtifactRefs: ["p32-export-committed-ref", versionRef],
      receipts: [receipt],
    },
    error: "",
    errorCode: "",
    dependencyStatus: "ready" as const,
    deferredReason: "",
    sourceArtifactRefs: ["p32-export-committed-ref", versionRef],
    loading: false,
    manifest: [
      {
        ordinal: 1,
        sceneRef: "scene-1",
        versionRef,
        heading: "内景 档案室 - 夜",
        blockCount: 3,
        actionBlocks: 1,
        dialogueBlocks: 1,
        valid: true,
      },
    ],
    reload: mocks.reload,
  }
}
