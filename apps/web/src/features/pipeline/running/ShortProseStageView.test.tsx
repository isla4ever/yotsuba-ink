// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import ShortProseStageView from "./ShortProseStageView"
import { ShortProseWorkbench } from "./ShortProseWorkbench"

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
    activeProject: {
      architectureVersion: "phase32-routes-v1",
      creationRouteId: "short_novel",
    },
    activeRun: runEnvelope("text"),
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
    const selected = unitRef || "unit-2"
    mocks.unitRefs.push(selected)
    const current = selected === "unit-2"
    const recovery = current && mocks.recovery
    return {
      change: vi.fn(),
      current: {
        artifact_ref: current
          ? recovery
            ? "p32-text-committed-unit-2"
            : "p32-text-candidate-unit-2"
          : "p32-text-committed-unit-1",
        editable: current && !recovery,
        pending_decision: current
          ? recovery
            ? writebackDecision("text", "unit-2", 7)
            : {
                allowed_actions: ["accept", "regenerate", "cancel"],
                artifact_ref: "p32-text-candidate-unit-2",
                decision_id: "decision-text-unit-2",
                domain_revision: 7,
                kind: "route_stage_decision",
                redraft_limit: 1,
                redraft_used: 0,
                stage_id: "text",
                unit_ref: "unit-2",
              }
          : null,
        status: current && !recovery ? "candidate" : "committed",
      },
      error: "",
      flush: mocks.flush,
      loading: false,
      payload: prosePayload(selected),
      status: current && !recovery ? "saved" : "readonly",
    }
  },
}))

vi.mock("../state/usePhase32ShortProseContext", () => ({
  usePhase32ShortProseContext: () => ({
    context: referenceContext(),
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("ShortProseStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.recovery = false
    mocks.unitRefs.length = 0
    mocks.flush.mockResolvedValue("p32-draft-text-unit-2")
    mocks.refreshRun.mockResolvedValue(runEnvelope("cover"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("cover"))
  })

  it("retries formal writeback without reopening or resaving accepted prose", async () => {
    mocks.recovery = true
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(<ShortProseStageView />)
      await Promise.resolve()
    })

    expect(container.textContent).toContain("正文安全，正式事实写回待恢复")
    expect(container.querySelector("textarea")).toBeNull()
    await act(async () => {
      findButton(container, "重试正式写回").click()
      await Promise.resolve()
    })

    expect(mocks.flush).not.toHaveBeenCalled()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-short-prose-1", {
      action: "retry_writeback",
      decisionId: "decision-writeback-unit-2",
      direction: undefined,
      domainRevision: 7,
      draftRef: undefined,
    })
    expect(mocks.setRoute).toHaveBeenCalledWith("cover")

    act(() => root.unmount())
  })

  it("browses accepted units in reading mode and accepts only the active unit", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(<ShortProseStageView />)
      await Promise.resolve()
    })

    const units = () =>
      container.querySelectorAll<HTMLButtonElement>(
        ".short-prose-rail-list > button",
      )
    expect(container.querySelector("textarea")).toBeNull()
    expect(container.textContent).toContain("她把证物袋压在胸前")

    await act(async () => {
      units()[0].click()
      await Promise.resolve()
    })
    expect(container.textContent).toContain("她把复印件贴近台灯")
    expect(container.textContent).toContain("当前正文已接受")
    expect(mocks.unitRefs.at(-1)).toBe("unit-1")

    await act(async () => {
      units()[1].click()
      await Promise.resolve()
    })
    const accept = findButton(container, "确认 U02")
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-short-prose-1", {
      action: "accept",
      decisionId: "decision-text-unit-2",
      direction: undefined,
      domainRevision: 7,
      draftRef: "p32-draft-text-unit-2",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("cover")

    act(() => root.unmount())
  })

  it("binds the editable manuscript selection to the current prose unit", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <ShortProseWorkbench
          activeUnitRef="unit-2"
          artifact={prosePayload("unit-2")}
          artifactRef="p32-text-candidate-unit-2"
          committedArtifactRefs={{
            "unit-1": "p32-text-committed-unit-1",
          }}
          editable
          expectedUnitKind="section"
          onChange={vi.fn()}
          onSelectUnit={vi.fn()}
          orderedUnitRefs={["unit-1", "unit-2"]}
          referenceContext={referenceContext()}
          revisionLabel="Unit 2 · Revision 3"
          selectedUnitRef="unit-2"
        />,
      ),
    )

    const manuscript = container.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="当前正文"]',
    )
    expect(manuscript?.dataset.collaborationFieldPath).toBe("content")
    expect(manuscript?.dataset.collaborationUnit).toBe("unit-2")

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
    definition: {
      run_id: "run-short-prose-1",
      scale_profile: {
        payload: {
          target: 20_000,
          recommended_ceiling: 30_000,
          unit: "characters",
        },
      },
    },
    read_model: {
      active_stage_id: activeStageId,
      active_unit_ref: activeStageId === "text" ? "unit-2" : "",
      pending_decisions:
        activeStageId === "text"
          ? [
              {
                allowed_actions: ["accept", "regenerate", "cancel"],
                artifact_ref: "p32-text-candidate-unit-2",
                decision_id: "decision-text-unit-2",
                domain_revision: 7,
                redraft_limit: 1,
                redraft_used: 0,
                stage_id: "text",
                unit_ref: "unit-2",
              },
            ]
          : [],
      sequential_stage_progress: {
        text: {
          ordered_unit_refs: ["unit-1", "unit-2"],
          committed_artifact_refs: {
            "unit-1": "p32-text-committed-unit-1",
          },
        },
      },
      stage_manifest: [
        { stage_id: "text", label: "小说正文" },
        { stage_id: "cover", label: "封面" },
      ],
      stage_status: { text: "awaiting_decision" },
      updated_at: "2026-08-24T22:00:00Z",
    },
  }
}

function prosePayload(unitRef: string) {
  const current = unitRef === "unit-2"
  return {
    unit_ref: unitRef,
    unit_kind: "section" as const,
    title: current ? "时间戳" : "复印件",
    pov_subject_ref: "maya",
    content: current
      ? "她把证物袋压在胸前。\n\n走廊尽头的门已经落锁。"
      : "她把复印件贴近台灯。\n\n水印日期比封存记录晚了三天。",
  }
}

function referenceContext() {
  return {
    anchors: [],
    cast: {
      maya: {
        displayName: "玛雅",
        ref: "maya",
        role: "档案记者",
        voice: "克制、具体",
      },
    },
    storyQuestion: "谁修改了公共档案的签名链？",
    units: [
      {
        unitRef: "unit-1",
        ordinal: 1,
        title: "复印件",
        dramaticJob: "确认复印件来自封存卷宗。",
        povSubjectRef: "maya",
        sceneLoad: "档案室核验。",
        handoff: "下一单元从水印日期矛盾开始。",
        softCharacterBudget: 3000,
        promiseRefs: [],
      },
      {
        unitRef: "unit-2",
        ordinal: 2,
        title: "时间戳",
        dramaticJob: "把日期矛盾变成可公开核验的签名链。",
        povSubjectRef: "maya",
        sceneLoad: "走廊拦截。",
        handoff: "证据进入公开听证。",
        softCharacterBudget: 3400,
        promiseRefs: [],
      },
    ],
  }
}
