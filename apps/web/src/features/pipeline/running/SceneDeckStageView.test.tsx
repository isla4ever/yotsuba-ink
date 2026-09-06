// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import SceneDeckStageView from "./SceneDeckStageView"

const mocks = vi.hoisted(() => ({
  flush: vi.fn(),
  reconnectRun: vi.fn(),
  refreshRun: vi.fn(),
  resolveDecision: vi.fn(),
  setRoute: vi.fn(),
}))

vi.mock("../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: { architectureVersion: "phase32-routes-v1" },
    activeRun: runEnvelope("scene_deck"),
    reconnectRun: mocks.reconnectRun,
    refreshRun: mocks.refreshRun,
    runError: "",
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../state/usePhase32ArtifactDraft", () => ({
  usePhase32ArtifactDraft: () => ({
    change: vi.fn(),
    current: {
      artifact_ref: "p32-scene-deck-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-scene-deck-1",
        domain_revision: 5,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: sceneDeckPayload(),
    status: "saved",
  }),
}))

vi.mock("../state/usePhase32SceneDeckContext", () => ({
  usePhase32SceneDeckContext: () => ({
    context: {
      beats: [],
      cast: { maya: { label: "玛雅", ref: "maya", role: "记者" } },
    },
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./SceneDeckArtifactEditor", () => ({
  SceneDeckArtifactEditor: () => <div>Scene Deck Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("SceneDeckStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-scene-deck-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("script"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("script"))
  })

  it("accepts the source-bound deck and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<SceneDeckStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认场景调度"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-scene-deck-1", {
      decisionId: "decision-scene-deck-1",
      action: "accept",
      domainRevision: 5,
      direction: undefined,
      draftRef: "p32-draft-scene-deck-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("script")

    act(() => root.unmount())
  })
})

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-scene-deck-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: {
        scene_deck: { artifact_ref: "candidate-scene-deck-1" },
      },
      pending_decisions: [{ stage_id: "scene_deck" }],
      stage_manifest: [
        { stage_id: "scene_deck", label: "场景调度" },
        { stage_id: "script", label: "剧本正文" },
      ],
      stage_status: { scene_deck: "awaiting_decision" },
      updated_at: "2026-08-24T20:00:00Z",
    },
  }
}

function sceneDeckPayload() {
  return {
    scenes: [
      {
        scene_ref: "scene-1",
        heading: "INT. 市档案馆 - NIGHT",
        location_and_time: "闭馆前十分钟",
        cast_subject_refs: ["maya"],
        visible_goal: "找到被替换的签名页。",
        opposition: "保安要求她立即离开。",
        outcome: "她取得带水印的复印件。",
        soft_page_target: 2.5,
      },
    ],
  }
}
