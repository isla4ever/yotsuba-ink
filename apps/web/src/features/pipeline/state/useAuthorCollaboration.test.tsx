// @vitest-environment happy-dom

import type { AppendMessage } from "@assistant-ui/react"
import { StrictMode, act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type {
  CollaborationContextReceipt,
  CollaborationSettingsEnvelope,
  CollaborationStreamEvent,
  CollaborationThread,
  CollaborationThreadDetail,
  SelectionAnchor,
} from "../contracts/authorCollaboration"
import {
  useAuthorCollaboration,
  type AuthorCollaborationController,
} from "./useAuthorCollaboration"

const mocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  getThread: vi.fn(),
  listThreads: vi.fn(),
  observe: vi.fn(),
  preview: vi.fn(),
  createThread: vi.fn(),
  createTurn: vi.fn(),
}))

vi.mock("../services/authorCollaborationApi", () => ({
  AuthorCollaborationApiError: class AuthorCollaborationApiError extends Error {
    code = "request_failed"
  },
  cancelCollaborationTurn: vi.fn(),
  createCollaborationThread: mocks.createThread,
  createCollaborationTurn: mocks.createTurn,
  deleteCollaborationThread: vi.fn(),
  getCollaborationSettings: mocks.getSettings,
  getCollaborationThread: mocks.getThread,
  listCollaborationThreads: mocks.listThreads,
  previewCollaborationContext: mocks.preview,
  rejectCollaborationPatch: vi.fn(),
  updateCollaborationThread: vi.fn(),
}))

vi.mock("../services/authorCollaborationStream", () => ({
  observeAuthorCollaboration: mocks.observe,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("useAuthorCollaboration lifecycle", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const threads = [thread("thread-a", "turn-1"), thread("thread-b", "turn-2")]
    mocks.listThreads.mockResolvedValue(threads)
    mocks.getThread.mockImplementation(
      async (_runId: string, threadId: string) =>
        detail(
          threads.find((item) => item.thread_id === threadId) ?? threads[0],
        ),
    )
    mocks.getSettings.mockResolvedValue(settingsEnvelope())
    mocks.observe.mockImplementation(() => () => undefined)
    mocks.preview.mockResolvedValue(receipt())
    mocks.createThread.mockImplementation(
      async (
        _runId: string,
        input: {
          source_ref?: string
          unit_ref?: string
        },
      ) =>
        thread(
          "thread-created",
          input.unit_ref ?? "artifact",
          input.source_ref ?? "story-map-v1",
        ),
    )
    mocks.createTurn.mockResolvedValue({})
  })

  it("survives the StrictMode effect remount and resets the SSE cursor before switching threads", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({
          anchors: [{ anchor_ref: "turn-1" }, { anchor_ref: "turn-2" }],
        }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(
        <StrictMode>
          <Harness />
        </StrictMode>,
      )
      await settleEffects()
    })

    expect(
      (controller as AuthorCollaborationController | null)?.activeThreadId,
    ).toBe("thread-a")
    expect(
      (controller as AuthorCollaborationController | null)?.detail?.thread
        .thread_id,
    ).toBe("thread-a")
    const firstSubscription = latestSubscription("thread-a")
    expect(firstSubscription?.options.after).toBe(0)

    await act(async () => {
      firstSubscription?.options.onEvent(streamEvent(7, "thread-a"))
      await settleEffects()
    })
    await act(async () => {
      ;(controller as AuthorCollaborationController | null)?.switchThread(
        "thread-b",
      )
      await settleEffects()
    })

    expect(
      (controller as AuthorCollaborationController | null)?.detail?.thread
        .thread_id,
    ).toBe("thread-b")
    expect(latestSubscription("thread-b")?.options.after).toBe(0)

    act(() => root.unmount())
  })

  it("keeps the first receipt pending when a selection switches to another scope thread", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({
          anchors: [{ anchor_ref: "turn-1" }, { anchor_ref: "turn-2" }],
        }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })
    await act(async () => {
      await requireController(controller).submit(
        appendMessage("请收紧第二个转折。"),
        selection(),
      )
      await settleEffects()
    })

    const activeController = requireController(controller)
    expect(activeController.activeThreadId).toBe("thread-b")
    expect(activeController.pendingSubmission?.threadId).toBe("thread-b")
    expect(activeController.latestReceipt?.receipt_id).toBe("receipt-1")

    act(() => root.unmount())
  })

  it("sends the selected context policy and Source Pack in the preview request", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({ anchors: [{ anchor_ref: "turn-1" }] }),
        enabled: true,
        knowledgeDocuments: [
          {
            doc_id: "kb-1",
            project_id: "project-1",
            title: "母带保管规范",
            filename: "rules.txt",
            chunk_count: 3,
            status: "indexed",
            parser: "plain-text",
            preview: "公开播放前核验来源与保管链。",
          },
        ],
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })
    act(() => {
      requireController(controller).setContextOption(
        "include_canon_wiki",
        false,
      )
      requireController(controller).toggleKnowledgeSource("kb-1")
    })
    await act(async () => {
      await requireController(controller).submit(
        appendMessage("核对母带公开规则。"),
        null,
      )
      await settleEffects()
    })

    expect(mocks.preview).toHaveBeenLastCalledWith(
      "run-1",
      "thread-a",
      expect.objectContaining({
        context_policy: expect.objectContaining({
          include_canon_wiki: false,
          include_knowledge: true,
          source_pack_refs: ["kb-1"],
        }),
      }),
    )
    expect(
      requireController(controller).pendingSubmission?.input.context_policy
        ?.source_pack_refs,
    ).toEqual(["kb-1"])

    act(() => root.unmount())
  })

  it("shows the lightweight reminder only before the second turn", async () => {
    const active = thread("thread-a", "turn-1")
    active.turn_count = 1
    mocks.listThreads.mockResolvedValue([active])
    mocks.getThread.mockImplementation(async () => detail(active))
    mocks.createTurn.mockImplementation(async () => {
      active.turn_count = 2
      return {}
    })
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({ anchors: [{ anchor_ref: "turn-1" }] }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })
    vi.useFakeTimers()
    await act(async () => {
      await requireController(controller).submit(
        appendMessage("第二轮问题。"),
        null,
      )
    })
    expect(requireController(controller).notice).toContain("本轮将继续采用")
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_600)
    })
    expect(requireController(controller).notice).toBe("")
    await act(async () => {
      await requireController(controller).submit(
        appendMessage("第三轮问题。"),
        null,
      )
    })
    expect(requireController(controller).notice).toBe("")
    vi.useRealTimers()

    act(() => root.unmount())
  })

  it("creates and reuses threads only for the current Artifact source and unit", async () => {
    mocks.listThreads.mockResolvedValue([
      thread("thread-old-source", "turn-1", "story-map-committed-old"),
      thread("thread-wrong-unit", "turn-2", "story-map-candidate-current"),
    ])
    mocks.getThread.mockImplementation(
      async (_runId: string, threadId: string) =>
        detail(
          threadId === "thread-created"
            ? thread("thread-created", "turn-1", "story-map-candidate-current")
            : thread("thread-old-source", "turn-1", "story-map-committed-old"),
        ),
    )
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({
          anchors: [{ anchor_ref: "turn-1" }, { anchor_ref: "turn-2" }],
        }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-candidate-current",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })

    expect(mocks.createThread).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        source_ref: "story-map-candidate-current",
        unit_ref: "turn-1",
      }),
    )
    expect(requireController(controller).activeThreadId).toBe("thread-created")
    expect(requireController(controller).sourceRef).toBe(
      "story-map-candidate-current",
    )

    act(() => root.unmount())
  })

  it("switches the active collaboration thread with the workbench secondary navigation scope", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness({ unitRef }: { unitRef: string }) {
      controller = useAuthorCollaboration({
        activeUnit: {
          label: unitRef === "turn-1" ? "转折一" : "转折二",
          unitRef,
        },
        artifactText: JSON.stringify({
          anchors: [{ anchor_ref: "turn-1" }, { anchor_ref: "turn-2" }],
        }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness unitRef="turn-1" />)
      await settleEffects()
    })
    expect(requireController(controller).activeThreadId).toBe("thread-a")

    await act(async () => {
      root.render(<Harness unitRef="turn-2" />)
      await settleEffects()
    })
    expect(requireController(controller).activeThreadId).toBe("thread-b")
    expect(requireController(controller).detail?.thread.scope.unit_ref).toBe(
      "turn-2",
    )

    act(() => root.unmount())
  })

  it("keeps unsent composer drafts isolated when switching collaboration threads", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({
          anchors: [{ anchor_ref: "turn-1" }, { anchor_ref: "turn-2" }],
        }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })
    act(() =>
      requireController(controller).setComposerDraft(
        "第一条线程尚未发送的推敲。",
      ),
    )
    expect(requireController(controller).composerDraft).toBe(
      "第一条线程尚未发送的推敲。",
    )

    await act(async () => {
      requireController(controller).switchThread("thread-b")
      await settleEffects()
    })
    expect(requireController(controller).composerDraft).toBe("")
    act(() =>
      requireController(controller).setComposerDraft("第二条线程的草稿。"),
    )

    await act(async () => {
      requireController(controller).switchThread("thread-a")
      await settleEffects()
    })
    expect(requireController(controller).composerDraft).toBe(
      "第一条线程尚未发送的推敲。",
    )
    expect(requireController(controller).hasComposerDraft("thread-b")).toBe(
      true,
    )

    act(() => root.unmount())
  })

  it("restores the exact first-turn request when the author abandons context confirmation", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null
    const request = "请重新推敲这段公开证据的代价。"

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({ anchors: [{ anchor_ref: "turn-1" }] }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })
    act(() => requireController(controller).setComposerDraft(request))
    await act(async () => {
      await requireController(controller).submit(appendMessage(request), null)
      await settleEffects()
    })
    expect(requireController(controller).composerDraft).toBe("")
    expect(requireController(controller).pendingSubmission?.input.message).toBe(
      request,
    )

    act(() => requireController(controller).dismissPendingSubmission())
    expect(requireController(controller).pendingSubmission).toBeNull()
    expect(requireController(controller).composerDraft).toBe(request)

    act(() => root.unmount())
  })

  it("keeps the same idempotent submission available when turn creation fails", async () => {
    const active = thread("thread-a", "turn-1")
    active.turn_count = 1
    mocks.listThreads.mockResolvedValue([active])
    mocks.getThread.mockImplementation(async () => detail(active))
    mocks.createTurn.mockRejectedValue(new Error("network unavailable"))
    const container = document.createElement("div")
    const root = createRoot(container)
    let controller: AuthorCollaborationController | null = null

    function Harness() {
      controller = useAuthorCollaboration({
        artifactText: JSON.stringify({ anchors: [{ anchor_ref: "turn-1" }] }),
        enabled: true,
        runId: "run-1",
        sourceRef: "story-map-v1",
        stageId: "story_map",
      })
      return null
    }

    await act(async () => {
      root.render(<Harness />)
      await settleEffects()
    })
    await act(async () => {
      await requireController(controller).submit(
        appendMessage("保持同一请求重试。"),
        null,
      )
      await settleEffects()
    })

    const pending = requireController(controller).pendingSubmission
    expect(pending?.input.message).toBe("保持同一请求重试。")
    expect(requireController(controller).error).toBe("network unavailable")
    expect(mocks.createTurn).toHaveBeenCalledWith(
      "run-1",
      "thread-a",
      expect.objectContaining({
        client_turn_id: pending?.input.client_turn_id,
        preview_signature: pending?.receipt.receipt_hash,
      }),
    )

    act(() => root.unmount())
  })
})

function latestSubscription(threadId: string) {
  const records = mocks.observe.mock.calls
    .map((call) => ({
      threadId: call[1] as string,
      options: call[2] as {
        after: number
        onEvent: (event: CollaborationStreamEvent) => void
      },
    }))
    .filter((record) => record.threadId === threadId)
  return records[records.length - 1]
}

function appendMessage(text: string): AppendMessage {
  return {
    role: "user",
    content: [{ type: "text", text }],
    attachments: [],
    createdAt: new Date("2026-08-21T00:00:00Z"),
    parentId: null,
    sourceId: null,
    runConfig: {},
    metadata: { custom: {} },
  }
}

function requireController(
  controller: AuthorCollaborationController | null,
): AuthorCollaborationController {
  if (!controller)
    throw new Error("Author collaboration controller is not ready")
  return controller
}

async function settleEffects() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
}

function thread(
  threadId: string,
  unitRef: string,
  sourceRef = "story-map-v1",
): CollaborationThread {
  return {
    architecture_version: "phase32-routes-v1",
    thread_id: threadId,
    run_id: "run-1",
    project_id: "project-1",
    creation_route_id: "short_novel",
    route_revision: "r3",
    stage_id: "story_map",
    artifact_kind: "story_map",
    scope: {
      artifact_ref: sourceRef,
      effective_payload_digest: "e".repeat(64),
      source_signature: "a".repeat(64),
      unit_ref: unitRef,
      field_path: "",
      label: unitRef,
    },
    title: `故事地图 · ${unitRef}`,
    provider_execution: {
      provider_profile_id: "provider-1",
      model_id: "model-1",
    } as CollaborationThread["provider_execution"],
    context_policy_id: "collaboration-default-v1",
    status: "active",
    turn_count: 0,
    has_unapplied_patch: false,
    created_at: "2026-08-21T00:00:00Z",
    updated_at: "2026-08-21T00:00:00Z",
  }
}

function detail(record: CollaborationThread): CollaborationThreadDetail {
  return { thread: record, turns: [], messages: [], patches: [] }
}

function settingsEnvelope(): CollaborationSettingsEnvelope {
  return {
    settings: {
      default_mode: "discuss",
      default_provider_profile_id: "provider-1",
      default_model: "model-1",
      context_policy: {
        policy_id: "collaboration-default-v1",
        version: 1,
        max_input_chars: 24_000,
        max_history_turns: 8,
        include_author_preferences: true,
        include_craft_mechanisms: true,
        include_knowledge: false,
        include_canon_wiki: true,
        include_foreshadow: true,
        author_preferences: "",
        craft_mechanisms: [],
        source_pack_refs: [],
      },
      history_retention_days: 180,
    },
    capabilities: [],
  }
}

function streamEvent(
  sequence: number,
  threadId: string,
): CollaborationStreamEvent {
  return {
    sequence,
    event_id: `event-${sequence}`,
    thread_id: threadId,
    turn_id: "",
    type: "thread.updated",
    payload: {},
    created_at: "2026-08-21T00:00:00Z",
  }
}

function selection(): SelectionAnchor {
  return {
    anchor_id: "selection-2",
    stage_id: "story_map",
    source_ref: "story-map-v1",
    unit_ref: "turn-2",
    field_path: "anchors.1.consequence_or_open_effect",
    field_hash: "b".repeat(64),
    selection_start: 0,
    selection_end: 4,
    selected_text_hash: "c".repeat(64),
    selected_char_count: 4,
    preview: "第二转折",
    selected_text: "第二转折",
    created_at: "2026-08-21T00:00:00Z",
  }
}

function receipt(): CollaborationContextReceipt {
  return {
    receipt_id: "receipt-1",
    thread_id: "thread-b",
    turn_id: "turn-1",
    run_id: "run-1",
    creation_route_id: "short_novel",
    route_revision: "r3",
    stage_id: "story_map",
    artifact_kind: "story_map",
    source_artifact_ref: "story-map-v1",
    source_signature: "a".repeat(64),
    effective_payload_digest: "e".repeat(64),
    sources: [],
    history_message_refs: [],
    budget_chars: 24_000,
    used_chars: 120,
    token_estimate: 60,
    provider_profile_id: "provider-1",
    model: "model-1",
    receipt_hash: "d".repeat(64),
    created_at: "2026-08-21T00:00:00Z",
  }
}
