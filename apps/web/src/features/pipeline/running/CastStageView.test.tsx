// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import CastStageView from "./CastStageView"

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
    activeRun: runEnvelope("cast"),
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
      artifact_ref: "p32-character-bible-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-cast-1",
        domain_revision: 5,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: castPayload(),
    status: "saved",
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./CastArtifactEditor", () => ({
  CastArtifactEditor: () => <div>Cast Artifact Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("CastStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-cast-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("section_plan"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("section_plan"))
  })

  it("commits the source-bound Cast aggregate and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<CastStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认人物圣经"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-cast-1", {
      decisionId: "decision-cast-1",
      action: "accept",
      domainRevision: 5,
      direction: undefined,
      draftRef: "p32-draft-cast-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("section_plan")

    act(() => root.unmount())
  })
})

function castPayload() {
  return {
    characters: [
      {
        subject_ref: "maya",
        display_name: "玛雅",
        role: "档案记者",
        desire: "查清被删去的真相",
        stakes: "失去职业与家人的信任",
        constraints: ["不能公开未经核实的证据"],
        voice: "短句，先核对事实再表达",
        arc_scope: "从旁观者变成承担后果的人",
      },
    ],
    relationships: [],
  }
}

function runEnvelope(activeStageId: string) {
  return {
    definition: {
      run_id: "run-cast-1",
      route_contract: { creation_route_id: "short_novel" },
    },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: { cast: { artifact_ref: "candidate-cast-1" } },
      pending_decisions: [{ stage_id: "cast" }],
      stage_manifest: [
        { stage_id: "cast", label: "人物圣经" },
        { stage_id: "section_plan", label: "章节规划" },
      ],
      stage_status: { cast: "awaiting_decision" },
      updated_at: "2026-08-23T17:00:00Z",
    },
  }
}
