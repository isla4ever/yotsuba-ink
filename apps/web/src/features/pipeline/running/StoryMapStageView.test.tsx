// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import StoryMapStageView from "./StoryMapStageView"

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
    activeRun: runEnvelope("story_map"),
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
      artifact_ref: "p32-story-map-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-story-map-1",
        domain_revision: 3,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: storyMapPayload(),
    status: "saved",
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./StoryMapArtifactEditor", () => ({
  StoryMapArtifactEditor: () => <div>Story Map Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("StoryMapStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-story-map-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("text"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("text"))
  })

  it("accepts the source-bound draft and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<StoryMapStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认故事地图"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-story-map-1", {
      decisionId: "decision-story-map-1",
      action: "accept",
      domainRevision: 3,
      direction: undefined,
      draftRef: "p32-draft-story-map-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("text")

    act(() => root.unmount())
  })
})

function storyMapPayload() {
  return {
    opening_state: "主角只相信公开档案。",
    story_question: "谁在修改城市记忆？",
    anchors: [
      {
        anchor_ref: "anchor-1",
        dramatic_job: "建立档案被篡改的压力。",
        pressure: "关键记录在公开前消失。",
        choice_or_revelation: "主角决定追查签名链。",
        consequence_or_open_effect: "她被卷入机构内部调查。",
        promise_refs: ["promise-truth-cost"],
      },
    ],
    ending_state: "真相公开，但主角失去原职。",
    open_questions: ["谁批准了最初的删改？"],
  }
}

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-story-map-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: { story_map: { artifact_ref: "candidate-1" } },
      pending_decisions: [{ stage_id: "story_map" }],
      stage_manifest: [
        { stage_id: "story_map", label: "故事地图" },
        { stage_id: "cast", label: "人物圣经" },
        { stage_id: "section_plan", label: "章节规划" },
        { stage_id: "text", label: "小说正文" },
      ],
      stage_status: { story_map: "awaiting_decision" },
      updated_at: "2026-08-23T10:00:00Z",
    },
  }
}
