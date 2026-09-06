// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import BeatBoardStageView from "./BeatBoardStageView"
import BookArchitectureStageView from "./BookArchitectureStageView"
import StoryMapStageView from "./StoryMapStageView"

const state = vi.hoisted(() => ({
  routeId: "screenplay_sample",
  stageId: "beat_board",
}))

const mocks = vi.hoisted(() => ({
  openProject: vi.fn(),
  refreshActiveProject: vi.fn(),
  refreshRun: vi.fn(),
  setRoute: vi.fn(),
}))

vi.mock("../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: {
      architectureVersion: "phase32-routes-v1",
      creationRouteId: state.routeId,
    },
    activeRun: runEnvelope(state.routeId, state.stageId),
    openProject: mocks.openProject,
    reconnectRun: vi.fn(),
    refreshActiveProject: mocks.refreshActiveProject,
    refreshRun: mocks.refreshRun,
    runError: "",
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../state/usePhase32ArtifactDraft", () => ({
  usePhase32ArtifactDraft: (_runId: string, stageId: string) => {
    const payload = payloadFor(stageId)
    return {
      change: vi.fn(),
      current: {
        artifact_kind: `${stageId}_artifact`,
        artifact_ref: `p32-${stageId}-committed-${"a".repeat(64)}`,
        creation_route_id: state.routeId,
        editable: false,
        payload,
        payload_digest: "a".repeat(64),
        pending_decision: null,
        run_id: "run-completed-1",
        stage_id: stageId,
        status: "committed",
        unit_ref: "",
      },
      error: "",
      flush: vi.fn(),
      loading: false,
      payload,
      status: "readonly",
    }
  },
}))

vi.mock("../state/usePhase32BeatBoardContext", () => ({
  usePhase32BeatBoardContext: () => ({
    context: { brief: {}, cast: {} },
    error: "",
    loading: false,
  }),
}))

vi.mock("../services/runApi", () => ({
  resolvePhase32RunDecision: vi.fn(),
}))

vi.mock("./BeatBoardArtifactEditor", () => ({
  BeatBoardArtifactEditor: ({ editable }: { editable: boolean }) => (
    <div data-testid="beat-editor">{editable ? "editing" : "reading"}</div>
  ),
}))

vi.mock("./StoryMapArtifactEditor", () => ({
  StoryMapArtifactEditor: ({ editable }: { editable: boolean }) => (
    <div data-testid="story-editor">{editable ? "editing" : "reading"}</div>
  ),
}))

vi.mock("./BookArchitectureArtifactEditor", () => ({
  BookArchitectureArtifactEditor: ({ editable }: { editable: boolean }) => (
    <div data-testid="book-editor">{editable ? "editing" : "reading"}</div>
  ),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("planning Artifact amendment route integration", () => {
  beforeEach(() => vi.clearAllMocks())

  it.each([
    ["screenplay_sample", "beat_board", BeatBoardStageView, "beat-editor"],
    ["short_novel", "story_map", StoryMapStageView, "story-editor"],
    [
      "long_novel",
      "book_architecture",
      BookArchitectureStageView,
      "book-editor",
    ],
  ])(
    "%s committed %s enters the shared formal amendment editor",
    async (routeId, stageId, View, editorTestId) => {
      state.routeId = routeId
      state.stageId = stageId
      const container = document.createElement("div")
      const root = createRoot(container)
      await act(async () => root.render(<View />))

      expect(
        container.querySelector(`[data-testid="${editorTestId}"]`)?.textContent,
      ).toBe("reading")
      const amend = container.querySelector<HTMLButtonElement>(
        'button[aria-label="正式修订已提交版本"]',
      )
      expect(amend?.textContent).toContain("修订")

      act(() => amend?.click())
      expect(
        container.querySelector(`[data-testid="${editorTestId}"]`)?.textContent,
      ).toBe("editing")
      expect(container.textContent).toContain("正式修订副本")

      act(() => root.unmount())
    },
  )
})

function runEnvelope(routeId: string, stageId: string) {
  const labels: Record<string, string> = {
    beat_board: "因果节拍",
    story_map: "故事地图",
    book_architecture: "全书架构",
  }
  return {
    definition: {
      run_id: "run-completed-1",
      route_contract: { creation_route_id: routeId },
    },
    read_model: {
      active_amendment_id: "",
      active_stage_id: stageId,
      artifact_refs: { [stageId]: { artifact_ref: `artifact-${stageId}` } },
      pending_decisions: [],
      stage_manifest: [{ stage_id: stageId, label: labels[stageId] }],
      stage_status: { [stageId]: "completed" },
      status: "completed",
      updated_at: "2026-08-25T13:00:00+08:00",
    },
  }
}

function payloadFor(stageId: string) {
  if (stageId === "beat_board") {
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
      ],
    }
  }
  if (stageId === "story_map") {
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
