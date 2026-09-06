// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import BookArchitectureStageView from "./BookArchitectureStageView"

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
    activeRun: runEnvelope("book_architecture"),
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
      artifact_ref: "p32-book-architecture-candidate-1",
      editable: true,
      pending_decision: {
        allowed_actions: ["accept", "regenerate", "cancel"],
        decision_id: "decision-book-architecture-1",
        domain_revision: 4,
        redraft_limit: 1,
        redraft_used: 0,
      },
      status: "candidate",
    },
    error: "",
    flush: mocks.flush,
    loading: false,
    payload: bookArchitecturePayload(),
    status: "saved",
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: mocks.resolveDecision,
}))

vi.mock("./BookArchitectureArtifactEditor", () => ({
  BookArchitectureArtifactEditor: () => <div>Book Architecture Editor</div>,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("BookArchitectureStageView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.flush.mockResolvedValue("p32-draft-book-architecture-1")
    mocks.refreshRun.mockResolvedValue(runEnvelope("volumes"))
    mocks.resolveDecision.mockResolvedValue(runEnvelope("volumes"))
  })

  it("accepts the source-bound aggregate and follows the backend active stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<BookArchitectureStageView />))

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认全书架构"),
    )!
    await act(async () => {
      accept.click()
      await Promise.resolve()
    })

    expect(mocks.flush).toHaveBeenCalledOnce()
    expect(mocks.resolveDecision).toHaveBeenCalledWith(
      "run-book-architecture-1",
      {
        decisionId: "decision-book-architecture-1",
        action: "accept",
        domainRevision: 4,
        direction: undefined,
        draftRef: "p32-draft-book-architecture-1",
      },
    )
    expect(mocks.refreshRun).toHaveBeenCalledOnce()
    expect(mocks.reconnectRun).toHaveBeenCalledOnce()
    expect(mocks.setRoute).toHaveBeenCalledWith("volumes")

    act(() => root.unmount())
  })
})

function bookArchitecturePayload() {
  return {
    book_promise: "一场关于城市记忆与公开代价的长期调查。",
    ending_conditions: ["证据链公开。"],
    parts: [
      {
        part_ref: "part-1",
        ordinal: 1,
        entry_state: "主角只相信公开档案。",
        dramatic_question: "她能否证明档案正在被系统性删改？",
        promise_refs: ["promise-truth"],
        turning_point_refs: ["turn-erasure"],
        exit_state: "第一份原始证据进入公众视野。",
        unresolved_obligations: ["找到签发删改命令的人。"],
      },
    ],
  }
}

function runEnvelope(activeStageId: string) {
  return {
    definition: { run_id: "run-book-architecture-1" },
    read_model: {
      active_stage_id: activeStageId,
      artifact_refs: {
        book_architecture: { artifact_ref: "candidate-architecture-1" },
      },
      pending_decisions: [{ stage_id: "book_architecture" }],
      stage_manifest: [
        { stage_id: "book_architecture", label: "全书架构" },
        { stage_id: "cast", label: "人物圣经" },
        { stage_id: "volumes", label: "卷册架构" },
      ],
      stage_status: { book_architecture: "awaiting_decision" },
      updated_at: "2026-08-23T15:00:00Z",
    },
  }
}
