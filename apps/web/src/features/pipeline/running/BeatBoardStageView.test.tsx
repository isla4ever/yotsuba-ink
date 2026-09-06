// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import BeatBoardStageView from "./BeatBoardStageView"

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
    activeRun: runEnvelope("beat_board"),
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
      artifact_ref: "p32-beat-board-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-beat-board-1",
        domain_revision: 4,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: beatBoardPayload(),
    status: "saved",
  }),
}))

vi.mock("../state/usePhase32BeatBoardContext", () => ({
  usePhase32BeatBoardContext: () => ({
    context: { brief: {}, cast: {} },
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./BeatBoardArtifactEditor", () => ({
  BeatBoardArtifactEditor: () => <div>Beat Board Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("BeatBoardStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-beat-board-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("scene_deck"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("scene_deck"))
  })

  it("accepts the source-bound board and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<BeatBoardStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认因果节拍"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-beat-board-1", {
      decisionId: "decision-beat-board-1",
      action: "accept",
      domainRevision: 4,
      direction: undefined,
      draftRef: "p32-draft-beat-board-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("scene_deck")

    act(() => root.unmount())
  })
})

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-beat-board-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: {
        beat_board: { artifact_ref: "candidate-beat-board-1" },
      },
      pending_decisions: [{ stage_id: "beat_board" }],
      stage_manifest: [
        { stage_id: "beat_board", label: "因果节拍" },
        { stage_id: "scene_deck", label: "场景卡组" },
      ],
      stage_status: { beat_board: "awaiting_decision" },
      updated_at: "2026-08-24T18:00:00Z",
    },
  }
}

function beatBoardPayload() {
  return {
    beats: [
      {
        beat_ref: "beat-1",
        dramatic_job: "迫使主角越权查档。",
        visible_pressure: "档案室即将关闭。",
        character_decision: "主角复制未授权记录。",
        outcome: "她留下可追查的证据。",
        setup_or_payoff_refs: ["setup-signature-chain"],
        timing_hint: "约 90 秒",
      },
      {
        beat_ref: "beat-2",
        dramatic_job: "让越权调查转化为公开风险。",
        visible_pressure: "保安封锁出口。",
        character_decision: "主角拒绝交出原件。",
        outcome: "证据进入公开记录。",
        setup_or_payoff_refs: ["payoff-public-record"],
        timing_hint: "约 120 秒",
      },
    ],
  }
}
