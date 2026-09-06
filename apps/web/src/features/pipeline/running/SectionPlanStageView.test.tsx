// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import SectionPlanStageView from "./SectionPlanStageView"

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
    activeRun: runEnvelope("section_plan"),
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
      artifact_ref: "p32-section-plan-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-section-plan-1",
        domain_revision: 4,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: sectionPlanPayload(),
    status: "saved",
  }),
}))

vi.mock("../state/usePhase32SectionPlanContext", () => ({
  usePhase32SectionPlanContext: () => ({
    context: { cast: {}, promises: {} },
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./SectionPlanArtifactEditor", () => ({
  SectionPlanArtifactEditor: () => <div>Section Plan Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("SectionPlanStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-section-plan-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("text"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("text"))
  })

  it("accepts the source-bound plan and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<SectionPlanStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认章节计划"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-section-plan-1", {
      decisionId: "decision-section-plan-1",
      action: "accept",
      domainRevision: 4,
      direction: undefined,
      draftRef: "p32-draft-section-plan-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("text")

    act(() => root.unmount())
  })
})

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-section-plan-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: {
        section_plan: { artifact_ref: "candidate-section-plan-1" },
      },
      pending_decisions: [{ stage_id: "section_plan" }],
      stage_manifest: [
        { stage_id: "section_plan", label: "章节计划" },
        { stage_id: "text", label: "正文" },
      ],
      stage_status: { section_plan: "awaiting_decision" },
      updated_at: "2026-08-24T16:00:00Z",
    },
  }
}

function sectionPlanPayload() {
  return {
    units: [
      {
        unit_ref: "unit-1",
        ordinal: 1,
        title: "封存前的签名",
        dramatic_job: "让主角获得第一条可独立核验的签名证据。",
        pov_subject_ref: "maya",
        scene_load: "档案室核验与走廊拦截。",
        handoff: "签名日期与封存命令发生冲突。",
        soft_character_budget: 3_000,
        promise_refs: [],
      },
    ],
  }
}
