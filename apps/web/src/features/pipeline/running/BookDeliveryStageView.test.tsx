// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import BookDeliveryStageView from "./BookDeliveryStageView"

const mocks = vi.hoisted(() => ({
  download: vi.fn(),
  deferred: false,
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
      creationRouteId: "short_novel",
    },
    activeRun: {
      definition: { run_id: "run-book-1" },
      read_model: { updated_at: "2026-08-24T12:00:00Z" },
    },
    runError: "",
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../state/usePhase32BookDelivery", () => ({
  usePhase32BookDelivery: () =>
    mocks.deferred ? deferredDeliveryState() : deliveryState(),
}))

vi.mock("../services/bookDeliveryApi", () => ({
  downloadBookDelivery: mocks.download,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("BookDeliveryStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.deferred = false
    mocks.download.mockResolvedValue(undefined)
  })

  it("renders the receipt manifest and downloads the frozen book", async () => {
    const container = document.createElement("div")
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<BookDeliveryStageView />))

    expect(container.querySelectorAll("input, textarea, select")).toHaveLength(
      0,
    )
    expect(container.textContent).toContain("被删去的城市")
    expect(container.textContent).toContain("失踪页")
    expect(container.textContent).toContain("2 committed")
    expect(container.querySelector("img")?.getAttribute("src")).toContain(
      "/cover-assets/asset-cover-1",
    )

    const docxFile = Array.from(container.querySelectorAll("button")).find(
      (button) =>
        button.textContent?.includes("DOCX") &&
        !button.textContent?.includes("下载"),
    )!
    act(() => docxFile.click())
    expect(container.textContent).toContain("被删去的城市.docx")

    const download = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("下载 DOCX"),
    )!
    await act(async () => {
      download.click()
      await Promise.resolve()
    })
    expect(mocks.download).toHaveBeenCalledWith(
      "run-book-1",
      expect.objectContaining({ export_id: "book-export-1-docx" }),
    )
    expect(container.textContent).toContain("已下载")

    const back = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("返回正式封面"),
    )!
    act(() => back.click())
    expect(mocks.setRoute).toHaveBeenCalledWith("cover")

    act(() => root.unmount())
    container.remove()
  })

  it("explains image-deferred delivery and routes back to Cover", async () => {
    mocks.deferred = true
    const container = document.createElement("div")
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<BookDeliveryStageView />))

    expect(container.textContent).toContain("正文已完成，成书交付暂缓")
    expect(container.textContent).toContain("DEPENDENCY DEFERRED")
    expect(container.textContent).toContain("图片验收尚未启用")
    expect(container.textContent).not.toContain("成书交付已冻结")

    const back = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("返回封面阶段"),
    )!
    act(() => back.click())
    expect(mocks.setRoute).toHaveBeenCalledWith("cover")

    act(() => root.unmount())
    container.remove()
  })
})

function deliveryState() {
  const epubReceipt = {
    export_id: "book-export-1-epub",
    run_id: "run-book-1",
    creation_route_id: "short_novel" as const,
    artifact_ref: "p32-export-committed-ref",
    artifact_digest: "a".repeat(64),
    format: "epub" as const,
    chapter_refs: ["section-1", "section-2"],
    chapter_version_refs: [version("b"), version("c")],
    chapter_manifest: manifest(),
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
  }
  const docxReceipt = {
    ...epubReceipt,
    export_id: "book-export-1-docx",
    format: "docx" as const,
    filename: "被删去的城市.docx",
    media_type:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    size_bytes: 5120,
    sha256: "f".repeat(64),
  }
  return {
    artifact: {
      title: "被删去的城市",
      author: "四叶墨",
      version_note: "锁定交付版",
      formats: ["epub", "docx"],
      chapter_refs: ["section-1", "section-2"],
      chapter_version_refs: [version("b"), version("c")],
      volume_refs: [],
      cover_asset_ref: "asset-cover-1",
    },
    artifactDigest: "a".repeat(64),
    envelope: {
      runId: "run-book-1",
      artifactRef: "p32-export-committed-ref",
      artifactDigest: "a".repeat(64),
      artifactType: "book_delivery" as const,
      dependencyStatus: "ready" as const,
      deferredReason: "",
      sourceArtifactRefs: [
        "p32-export-committed-ref",
        version("b"),
        version("c"),
      ],
      receipts: [epubReceipt, docxReceipt],
    },
    error: "",
    errorCode: "",
    dependencyStatus: "ready" as const,
    deferredReason: "",
    sourceArtifactRefs: [
      "p32-export-committed-ref",
      version("b"),
      version("c"),
    ],
    loading: false,
    manifest: manifest(),
    reload: mocks.reload,
  }
}

function deferredDeliveryState() {
  return {
    ...deliveryState(),
    artifact: null,
    artifactDigest: "",
    artifactRef: "",
    envelope: null,
    error: "图片验收尚未启用，当前 Run 仅完成 CoverBrief，暂不可导出成书。",
    errorCode: "image_deferred",
    dependencyStatus: "deferred" as const,
    deferredReason: "image_acceptance_not_in_current_wave",
    sourceArtifactRefs: ["p32-cover-committed-ref"],
    manifest: [],
  }
}

function manifest() {
  return [
    {
      ordinal: 1,
      chapter_ref: "section-1",
      version_ref: version("b"),
      title: "失踪页",
      unit_kind: "chapter" as const,
      volume_ref: "",
      character_count: 1280,
    },
    {
      ordinal: 2,
      chapter_ref: "section-2",
      version_ref: version("c"),
      title: "公开记录",
      unit_kind: "chapter" as const,
      volume_ref: "",
      character_count: 1630,
    },
  ]
}

function version(character: string) {
  return `p32-text-committed-${character.repeat(64)}`
}
