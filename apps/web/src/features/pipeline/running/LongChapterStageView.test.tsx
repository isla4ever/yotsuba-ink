// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import LongChapterStageView from "./LongChapterStageView"
import { LongChapterWorkbench } from "./LongChapterWorkbench"

const mocks = vi.hoisted(() => ({
  flush: vi.fn(),
  reconnectRun: vi.fn(),
  recovery: false,
  refreshRun: vi.fn(),
  resolveDecision: vi.fn(),
  setRoute: vi.fn(),
  chapterRefs: [] as string[],
}))

vi.mock("../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: {
      architectureVersion: "phase32-routes-v1",
      creationRouteId: "long_novel",
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
    const selected = unitRef || "chapter-2"
    mocks.chapterRefs.push(selected)
    const current = selected === "chapter-2"
    const recovery = current && mocks.recovery
    return {
      change: vi.fn(),
      current: {
        artifact_ref: current
          ? recovery
            ? "p32-text-committed-chapter-2"
            : "p32-text-candidate-chapter-2"
          : "p32-text-committed-chapter-1",
        editable: current && !recovery,
        pending_decision: current
          ? recovery
            ? writebackDecision("text", "chapter-2", 9)
            : {
                allowed_actions: ["accept", "regenerate", "cancel"],
                artifact_ref: "p32-text-candidate-chapter-2",
                decision_id: "decision-text-chapter-2",
                domain_revision: 9,
                kind: "route_stage_decision",
                redraft_limit: 1,
                redraft_used: 0,
                stage_id: "text",
                unit_ref: "chapter-2",
              }
          : null,
        status: current && !recovery ? "candidate" : "committed",
      },
      error: "",
      flush: mocks.flush,
      loading: false,
      payload: chapterPayload(selected),
      status: current && !recovery ? "saved" : "readonly",
    }
  },
}))

vi.mock("../state/usePhase32LongChapterContext", () => ({
  usePhase32LongChapterContext: () => ({
    context: referenceContext(),
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("LongChapterStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.recovery = false
    mocks.chapterRefs.length = 0
    mocks.flush.mockResolvedValue("p32-draft-text-chapter-2")
    mocks.refreshRun.mockResolvedValue(runEnvelope("cover"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("cover"))
  })

  it("retries formal writeback without reopening or resaving the accepted chapter", async () => {
    mocks.recovery = true
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(<LongChapterStageView />)
      await Promise.resolve()
    })

    expect(container.textContent).toContain("正文安全，正式事实写回待恢复")
    expect(container.querySelector("textarea")).toBeNull()
    await act(async () => {
      findButton(container, "重试正式写回").click()
      await Promise.resolve()
    })

    expect(mocks.flush).not.toHaveBeenCalled()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-long-chapter-1", {
      action: "retry_writeback",
      decisionId: "decision-writeback-chapter-2",
      direction: undefined,
      domainRevision: 9,
      draftRef: undefined,
    })
    expect(mocks.setRoute).toHaveBeenCalledWith("cover")

    act(() => root.unmount())
  })

  it("reads accepted chapters and accepts only the current chapter", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(<LongChapterStageView />)
      await Promise.resolve()
    })

    const chapters = () =>
      container.querySelectorAll<HTMLButtonElement>(
        ".long-chapter-rail-tree section > button",
      )
    expect(container.querySelector("textarea")).toBeNull()
    expect(container.textContent).toContain("走廊尽头的门已经落锁")

    await act(async () => {
      chapters()[0].click()
      await Promise.resolve()
    })
    expect(container.textContent).toContain("水印日期比封存记录晚了三天")
    expect(container.textContent).toContain("当前章节已接受")
    expect(mocks.chapterRefs.at(-1)).toBe("chapter-1")

    await act(async () => {
      chapters()[1].click()
      await Promise.resolve()
    })
    await act(async () => {
      findButton(container, "确认 CH02").click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith("run-long-chapter-1", {
      action: "accept",
      decisionId: "decision-text-chapter-2",
      direction: undefined,
      domainRevision: 9,
      draftRef: "p32-draft-text-chapter-2",
    })
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("cover")

    act(() => root.unmount())
  })

  it("binds the editable manuscript selection to the selected chapter", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <LongChapterWorkbench
          activeChapterRef="chapter-2"
          artifact={chapterPayload("chapter-2")}
          artifactRef="p32-text-candidate-chapter-2"
          committedArtifactRefs={{
            "chapter-1": "p32-text-committed-chapter-1",
          }}
          editable
          onChange={vi.fn()}
          onSelectChapter={vi.fn()}
          orderedChapterRefs={["chapter-1", "chapter-2"]}
          referenceContext={referenceContext()}
          revisionLabel="Chapter 2 · Revision 3"
          selectedChapterRef="chapter-2"
        />,
      ),
    )

    const manuscript = container.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="当前章节正文"]',
    )
    expect(manuscript?.dataset.collaborationFieldPath).toBe("content")
    expect(manuscript?.dataset.collaborationUnit).toBe("chapter-2")

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
      run_id: "run-long-chapter-1",
      scale_profile: { payload: { target: 150_000, unit: "characters" } },
    },
    read_model: {
      active_stage_id: activeStageId,
      active_unit_ref: activeStageId === "text" ? "chapter-2" : "",
      pending_decisions:
        activeStageId === "text"
          ? [
              {
                allowed_actions: ["accept", "regenerate", "cancel"],
                artifact_ref: "p32-text-candidate-chapter-2",
                decision_id: "decision-text-chapter-2",
                domain_revision: 9,
                redraft_limit: 1,
                redraft_used: 0,
                stage_id: "text",
                unit_ref: "chapter-2",
              },
            ]
          : [],
      sequential_stage_progress: {
        text: {
          ordered_unit_refs: ["chapter-1", "chapter-2"],
          committed_artifact_refs: {
            "chapter-1": "p32-text-committed-chapter-1",
          },
        },
      },
      stage_manifest: [
        { stage_id: "text", label: "逐章正文" },
        { stage_id: "cover", label: "封面" },
      ],
      stage_status: { text: "awaiting_decision" },
      updated_at: "2026-08-24T22:00:00Z",
    },
  }
}

function chapterPayload(chapterRef: string) {
  const current = chapterRef === "chapter-2"
  return {
    chapter_ref: chapterRef,
    volume_ref: "volume-1",
    title: current ? "异常封存" : "第一份证据",
    pov_subject_ref: "maya",
    content: current
      ? "她把证物袋压在胸前。\n\n走廊尽头的门已经落锁。"
      : "她把复印件贴近台灯。\n\n水印日期比封存记录晚了三天。",
  }
}

function referenceContext() {
  return {
    bookPromise: "公共记忆最终由谁书写？",
    cast: {
      maya: {
        displayName: "玛雅",
        role: "档案记者",
        voice: "克制、具体",
      },
    },
    chapters: [
      chapterPlan("chapter-1", 1, "第一份证据", "确认水印日期异常。"),
      chapterPlan("chapter-2", 2, "异常封存", "追查封存审批签名。"),
    ],
    parts: {
      "part-1": {
        ordinal: 1,
        dramaticQuestion: "她能否公开证据？",
        entryState: "证据无法核验",
        exitState: "证据进入公共记录",
      },
    },
    volumes: {
      "volume-1": {
        ordinal: 1,
        partRef: "part-1",
        promise: "追出签名链",
        conflict: "机构阻止公开核验",
      },
    },
  }
}

function chapterPlan(
  chapterRef: string,
  ordinal: number,
  title: string,
  dramaticJob: string,
) {
  return {
    chapterRef,
    ordinal,
    windowRef: "window-1",
    windowOrdinal: 1,
    volumeRef: "volume-1",
    title,
    povSubjectRef: "maya",
    castSubjectRefs: ["maya"],
    dramaticJob,
    entryState: "证据尚未公开",
    conflict: "档案权限即将关闭",
    stakes: "证据链可能失效",
    exitState: "得到可追溯签名",
    hook: "审批人已经失联",
    handoff: "下一章从审批人失联继续。",
    lengthHint: 3200,
    scenes: [
      {
        sceneRef: `scene-${ordinal}`,
        location: "档案馆",
        timeContext: "深夜",
        goal: "锁定签名链",
        opposition: "权限即将关闭",
        outcome: "得到审批签名",
      },
    ],
  }
}
