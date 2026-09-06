// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import VolumeArchitectureStageView from "./VolumeArchitectureStageView"

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
    activeRun: runEnvelope("volumes"),
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
      artifact_ref: "p32-volumes-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-volumes-1",
        domain_revision: 5,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: volumePayload(),
    status: "saved",
  }),
}))

vi.mock("../state/usePhase32VolumeContext", () => ({
  usePhase32VolumeContext: () => ({
    context: { cast: {}, parts: {} },
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./VolumeArchitectureArtifactEditor", () => ({
  VolumeArchitectureArtifactEditor: () => <div>Volume Architecture Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("VolumeArchitectureStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-volumes-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("rolling_detail"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("rolling_detail"))
  })

  it("accepts the source-bound aggregate and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<VolumeArchitectureStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认卷册架构"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-volumes-1", {
      decisionId: "decision-volumes-1",
      action: "accept",
      domainRevision: 5,
      direction: undefined,
      draftRef: "p32-draft-volumes-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("rolling_detail")

    act(() => root.unmount())
  })
})

function volumePayload() {
  return {
    volumes: [
      {
        volume_ref: "volume-1",
        ordinal: 1,
        part_ref: "part-1",
        promise: "找到第一份原始档案。",
        conflict: "机构试图销毁备份。",
        climax: "主角在听证会上提交证据。",
        closure: "调查进入公众视野。",
        cast_subject_refs: ["maya"],
        length_hint: 40_000,
      },
    ],
  }
}

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-volumes-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: {
        volumes: { artifact_ref: "candidate-volumes-1" },
      },
      pending_decisions: [{ stage_id: "volumes" }],
      stage_manifest: [
        { stage_id: "volumes", label: "卷册架构" },
        { stage_id: "rolling_detail", label: "滚动细纲" },
      ],
      stage_status: { volumes: "awaiting_decision" },
      updated_at: "2026-08-23T15:00:00Z",
    },
  }
}
