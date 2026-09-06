// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import Phase32CoverStageView from "./Phase32CoverStageView"

const mocks = vi.hoisted(() => ({
  flush: vi.fn(),
  reconnectRun: vi.fn(),
  refreshRun: vi.fn(),
  resolve: vi.fn(),
  selectAsset: vi.fn(),
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
      title: "被删去的城市",
    },
    activeRun: {
      definition: { run_id: "run-cover-1" },
      read_model: {
        active_stage_id: "cover",
        artifact_refs: {},
        pending_decisions: [{ stage_id: "cover" }],
        stage_manifest: [{ stage_id: "export", label: "成书交付" }],
        stage_status: { cover: "awaiting_decision" },
        updated_at: "2026-08-24T12:00:00Z",
      },
    },
    reconnectRun: mocks.reconnectRun,
    refreshRun: mocks.refreshRun,
    runError: "",
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../state/usePhase32Cover", () => ({
  usePhase32Cover: () => coverState(),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolve,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("Phase32CoverStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("draft-cover-1")
    mocks.refreshRun.mockResolvedValue(undefined)
    mocks.resolve.mockResolvedValue({
      read_model: { active_stage_id: "export" },
    })
  })

  it("selects a real candidate and commits the source-bound cover draft", async () => {
    const container = document.createElement("div")
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<Phase32CoverStageView />))

    expect(container.querySelectorAll("input, textarea, select")).toHaveLength(
      0,
    )
    expect(container.textContent).toContain("被删去的城市")
    expect(container.textContent).toContain("SELECTED AS FINAL")

    const secondCandidate = container.querySelector(
      'button[aria-label^="选择封面候选 2"]',
    ) as HTMLButtonElement
    act(() => secondCandidate.click())
    expect(mocks.selectAsset).toHaveBeenCalledWith("asset-cover-2")

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认正式封面"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolve).toHaveBeenCalledWith(
      "run-cover-1",
      expect.objectContaining({
        action: "accept",
        decisionId: "decision-cover-1",
        draftRef: "draft-cover-1",
      }),
    )
    expect(mocks.setRoute).toHaveBeenCalledWith("export")

    act(() => root.unmount())
    container.remove()
  })
})

function coverState() {
  return {
    artifact: {
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
    },
    artifactError: "",
    assetError: "",
    assets: [asset("asset-cover-1", 1), asset("asset-cover-2", 2)],
    assetStatus: "ready",
    current: {
      artifact_ref: "p32-cover-candidate-ref",
      editable: true,
      pending_decision: {
        decision_id: "decision-cover-1",
        domain_revision: 7,
        allowed_actions: ["accept", "regenerate", "cancel"],
        redraft_used: 0,
        redraft_limit: 1,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    generationAttempt: 1,
    loading: false,
    selectAsset: mocks.selectAsset,
    status: "saved",
  }
}

function asset(assetId: string, candidateIndex: number) {
  return {
    asset_id: assetId,
    run_id: "run-cover-1",
    operation_key: `run-cover-1:cover:image:${candidateIndex}`,
    candidate_index: candidateIndex,
    generation_attempt: 1,
    sha256: String(candidateIndex).repeat(64),
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
