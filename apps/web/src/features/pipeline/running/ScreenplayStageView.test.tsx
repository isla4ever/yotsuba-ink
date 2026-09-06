// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import ScreenplayStageView from "./ScreenplayStageView"

const mocks = vi.hoisted(() => ({
  flush: vi.fn(),
  reconnectRun: vi.fn(),
  recovery: false,
  refreshRun: vi.fn(),
  resolveDecision: vi.fn(),
  setRoute: vi.fn(),
  unitRefs: [] as string[],
}))

vi.mock("../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: { architectureVersion: "phase32-routes-v1" },
    activeRun: runEnvelope("script"),
    reconnectRun: mocks.reconnectRun,
    refreshRun: mocks.refreshRun,
    runError: "",
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../state/useArtifactEditMode", () => ({
  useArtifactEditMode: () => ({ editing: false, edit: vi.fn(), show: vi.fn() }),
}))

vi.mock("../state/usePhase32ArtifactDraft", () => ({
  usePhase32ArtifactDraft: (
    _runId: string,
    _stageId: string,
    _authorityRevision: string,
    _enabled: boolean,
    unitRef: string,
  ) => {
    const selected = unitRef || "scene-2"
    mocks.unitRefs.push(selected)
    const current = selected === "scene-2"
    const recovery = current && mocks.recovery
    return {
      change: vi.fn(),
      current: {
        artifact_ref: current
          ? recovery
            ? "p32-script-committed-scene-2"
            : "p32-script-candidate-scene-2"
          : "p32-script-committed-scene-1",
        editable: current && !recovery,
        pending_decision: current
          ? recovery
            ? writebackDecision("script", "scene-2", 7)
            : {
                allowed_actions: ["accept", "regenerate", "cancel"],
                artifact_ref: "p32-script-candidate-scene-2",
                decision_id: "decision-script-scene-2",
                domain_revision: 7,
                kind: "route_stage_decision",
                redraft_limit: 1,
                redraft_used: 0,
                stage_id: "script",
                unit_ref: "scene-2",
              }
          : null,
        status: current && !recovery ? "candidate" : "committed",
      },
      error: "",
      flush: mocks.flush,
      loading: false,
      payload: screenplayPayload(selected),
      status: current && !recovery ? "saved" : "readonly",
    }
  },
}))

vi.mock("../state/usePhase32ScreenplayContext", () => ({
  usePhase32ScreenplayContext: () => ({
    context: referenceContext(),
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("ScreenplayStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.recovery = false
    mocks.unitRefs.length = 0
    mocks.flush.mockResolvedValue("p32-draft-script-scene-2")
    mocks.refreshRun.mockResolvedValue(runEnvelope("export"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("export"))
  })

  it("retries formal writeback without reopening or resaving the accepted Scene", async () => {
    mocks.recovery = true
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(<ScreenplayStageView />)
      await Promise.resolve()
    })

    expect(container.textContent).toContain("正文安全，正式事实写回待恢复")
    expect(container.textContent).not.toContain("换稿 -/-")
    act(() => findButton(container, "取消 Run").click())
    expect(container.textContent).toContain("取消当前创作 Run？")
    act(() => findButton(container, "返回").click())
    expect(container.textContent).not.toContain("取消当前创作 Run？")
    await act(async () => {
      findButton(container, "重试正式写回").click()
      await Promise.resolve()
    })

    expect(mocks.flush).not.toHaveBeenCalled()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-screenplay-1", {
      action: "retry_writeback",
      decisionId: "decision-writeback-scene-2",
      direction: undefined,
      domainRevision: 7,
      draftRef: undefined,
    })
    expect(mocks.setRoute).toHaveBeenCalledWith("export")

    act(() => root.unmount())
  })

  it("keeps accepted scenes browsable and accepts only the active Scene", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(<ScreenplayStageView />)
      await Promise.resolve()
    })

    const scenes = () =>
      container.querySelectorAll<HTMLButtonElement>(
        ".screenplay-rail-list > button",
      )
    expect(container.textContent).toContain("玛雅冲进走廊")

    await act(async () => {
      scenes()[0].click()
      await Promise.resolve()
    })
    expect(container.textContent).toContain("玛雅翻开档案盒")
    expect(container.textContent).toContain("当前场次已接受")
    expect(mocks.unitRefs.at(-1)).toBe("scene-1")

    await act(async () => {
      scenes()[1].click()
      await Promise.resolve()
    })
    const accept = findButton(container, "确认 S02")
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-screenplay-1", {
      action: "accept",
      decisionId: "decision-script-scene-2",
      direction: undefined,
      domainRevision: 7,
      draftRef: "p32-draft-script-scene-2",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("export")

    act(() => root.unmount())
  })
})

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  return button
}

function writebackDecision(stageId: string, unitRef: string, revision: number) {
  return {
    allowed_actions: ["retry_writeback", "cancel"],
    artifact_ref: `p32-${stageId}-committed-${unitRef}`,
    decision_id: `decision-writeback-${unitRef}`,
    domain_revision: revision,
    kind: "writeback_recovery",
    redraft_limit: null,
    redraft_used: null,
    stage_id: stageId,
    unit_ref: unitRef,
  }
}

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-screenplay-1" },
    read_model: {
      active_stage_id: activeStageId,
      active_unit_ref: activeStageId === "script" ? "scene-2" : "",
      artifact_refs: {
        cast: { artifact_ref: "p32-cast-committed-1" },
        scene_deck: { artifact_ref: "p32-scene-deck-committed-1" },
      },
      pending_decisions:
        activeStageId === "script"
          ? [
              {
                allowed_actions: ["accept", "regenerate", "cancel"],
                artifact_ref: "p32-script-candidate-scene-2",
                decision_id: "decision-script-scene-2",
                domain_revision: 7,
                redraft_limit: 1,
                redraft_used: 0,
                stage_id: "script",
                unit_ref: "scene-2",
              },
            ]
          : [],
      sequential_stage_progress: {
        script: {
          ordered_unit_refs: ["scene-1", "scene-2"],
          committed_artifact_refs: {
            "scene-1": "p32-script-committed-scene-1",
          },
        },
      },
      stage_manifest: [
        { stage_id: "script", label: "剧本正文" },
        { stage_id: "export", label: "剧本交付" },
      ],
      stage_status: { script: "awaiting_decision" },
      updated_at: "2026-08-24T20:00:00Z",
    },
  }
}

function screenplayPayload(sceneRef: string) {
  const current = sceneRef === "scene-2"
  return {
    scene_ref: sceneRef,
    blocks: [
      {
        kind: "scene_heading",
        text: current ? "INT. 市档案馆走廊 - NIGHT" : "INT. 市档案馆 - NIGHT",
      },
      {
        kind: "action",
        text: current ? "玛雅冲进走廊，警卫已经锁住出口。" : "玛雅翻开档案盒。",
      },
    ],
  }
}

function referenceContext() {
  return {
    cast: {
      maya: {
        displayName: "玛雅",
        ref: "maya",
        role: "档案记者",
        voice: "克制",
      },
      guard: {
        displayName: "周警卫",
        ref: "guard",
        role: "保安",
        voice: "程序化",
      },
    },
    scenes: [
      {
        sceneRef: "scene-1",
        heading: "INT. 市档案馆 - NIGHT",
        locationAndTime: "闭馆前十分钟",
        castSubjectRefs: ["maya"],
        visibleGoal: "找到被替换的签名页。",
        opposition: "保安要求她立即离开。",
        outcome: "她取得带水印的复印件。",
        softPageTarget: 2.5,
      },
      {
        sceneRef: "scene-2",
        heading: "INT. 市档案馆走廊 - NIGHT",
        locationAndTime: "闭馆前五分钟",
        castSubjectRefs: ["maya", "guard"],
        visibleGoal: "把证据带出档案馆。",
        opposition: "保安封锁出口。",
        outcome: "证据公开，玛雅身份暴露。",
        softPageTarget: 2,
      },
    ],
  }
}
