// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import RollingDetailStageView from "./RollingDetailStageView"

const mocks = vi.hoisted(() => ({
  activeRun: null as unknown,
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
    activeRun: mocks.activeRun,
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
      artifact_ref: "p32-rolling-detail-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-rolling-detail-1",
        domain_revision: 6,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: detailPayload(),
    status: "clean",
  }),
}))

vi.mock("../state/usePhase32RollingDetailContext", () => ({
  usePhase32RollingDetailContext: () => ({
    context: { cast: {}, volumes: {}, volumeCast: {} },
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./RollingDetailArtifactEditor", () => ({
  RollingDetailArtifactEditor: () => <div>Rolling Detail Editor</div>,
}))

vi.mock("./ContractRepairWorkbench", () => ({
  ContractRepairWorkbench: () => <div>Contract Repair Workbench</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("RollingDetailStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.activeRun = runEnvelope("rolling_detail")
    mocks.flush.mockResolvedValue("p32-draft-rolling-detail-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("text"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("text"))
  })

  it("accepts the source-bound aggregate and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<RollingDetailStageView />))

    expect(container.textContent).toContain("当前候选")
    expect(container.textContent).not.toContain("原始候选")

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认当前细纲"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-detail-1", {
      decisionId: "decision-rolling-detail-1",
      action: "accept",
      domainRevision: 6,
      direction: undefined,
      draftRef: "p32-draft-rolling-detail-1",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("text")

    act(() => root.unmount())
  })

  it("routes a Rolling Detail Provider contract failure into quarantine repair", async () => {
    mocks.activeRun = {
      ...runEnvelope("rolling_detail"),
      read_model: {
        ...runEnvelope("rolling_detail").read_model,
        status: "failed",
        artifact_refs: {},
        pending_decisions: [],
        stage_status: { rolling_detail: "failed" },
        failure: {
          code: "provider_contract_failed",
          stage_id: "rolling_detail",
          unit_ref: "",
          retryable: false,
          message: "人物范围合同失败",
        },
      },
    }
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<RollingDetailStageView />))

    expect(container.textContent).toContain("Contract Repair Workbench")
    expect(container.textContent).not.toContain("滚动细纲尚未生成")

    act(() => root.unmount())
  })
})

function detailPayload() {
  return {
    windows: [
      {
        window_ref: "window-1",
        ordinal: 1,
        volume_refs: ["volume-1"],
        entry_state: "主角拿到复印件。",
        handoff: "下一窗口进入听证准备。",
        next_window_entry_state: "公众开始关注调查。",
        chapters: [
          {
            chapter_ref: "chapter-1",
            ordinal: 1,
            volume_ref: "volume-1",
            title: "第一份证据",
            pov_subject_ref: "maya",
            cast_subject_refs: ["maya"],
            dramatic_job: "建立第一条证据链。",
            entry_state: "主角只有来源不明的复印件。",
            conflict: "离馆期限与核验冲突。",
            stakes: "失败会让证据失去价值。",
            exit_state: "主角确认水印来源。",
            hook: "水印日期异常。",
            handoff: "下一章追查封存日期。",
            length_hint: 3_000,
            scenes: [
              {
                scene_ref: "scene-1",
                ordinal: 1,
                location: "市档案馆",
                time_context: "闭馆前",
                cast_subject_refs: ["maya"],
                goal: "核对水印。",
                opposition: "值班员催促离开。",
                outcome: "确认复印件来自封存卷宗。",
              },
            ],
          },
        ],
      },
    ],
  }
}

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-detail-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: {
        rolling_detail: { artifact_ref: "candidate-detail-1" },
      },
      pending_decisions: [{ stage_id: "rolling_detail" }],
      stage_manifest: [
        { stage_id: "rolling_detail", label: "滚动细纲" },
        { stage_id: "text", label: "正文" },
      ],
      stage_status: { rolling_detail: "awaiting_decision" },
      updated_at: "2026-08-24T10:00:00Z",
    },
  }
}
