// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"
import type {
  ArtifactPatchCandidate,
  CollaborationContextPolicy,
  CollaborationContextReceipt,
  CollaborationTurn,
} from "../../contracts/authorCollaboration"
import { ContextSourcePicker } from "./ContextSourcePicker"
import { ContextReceiptDialog } from "./ContextReceiptDialog"
import { PatchCandidateView } from "./PatchCandidateView"
import { CollaborationTurnOutcome } from "./CollaborationTurnOutcome"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("author collaboration decision surfaces", () => {
  it("distinguishes cancelled, failed, and unknown-outcome recovery states", () => {
    const cancelled = renderToStaticMarkup(
      <CollaborationTurnOutcome turn={turn("cancelled")} />,
    )
    const failed = renderToStaticMarkup(
      <CollaborationTurnOutcome turn={turn("failed")} />,
    )
    const unknown = renderToStaticMarkup(
      <CollaborationTurnOutcome
        turn={turn("failed", "provider_outcome_unknown")}
      />,
    )

    expect(cancelled).toContain("本轮已停止")
    expect(failed).toContain("本轮生成失败")
    expect(unknown).toContain("避免重复计费")
  })
  it("renders a source-bound before/after decision instead of applying silently", () => {
    const proposed = renderToStaticMarkup(
      <PatchCandidateView
        before="主角发现真相"
        disabled={false}
        onReject={() => undefined}
        patch={patch("proposed")}
      />,
    )
    const stale = renderToStaticMarkup(
      <PatchCandidateView
        before="主角发现真相"
        disabled={false}
        onReject={() => undefined}
        patch={patch("stale")}
      />,
    )

    expect(proposed).toContain("主角发现真相")
    expect(proposed).toContain("主角公开证据并承担代价")
    expect(proposed).toContain("版本修订接入后可写回")
    expect(proposed).toContain("保留原文")
    expect(stale).toContain("原文已变化")
    expect(stale).not.toContain("应用到当前稿")
  })

  it("keeps the pending request visible in the first full receipt and allows explicit abandonment", async () => {
    const root = createRoot(document.createElement("div"))
    const onCancelPending = vi.fn()

    await act(async () => {
      root.render(
        <ContextReceiptDialog
          confirmPending
          onCancelPending={onCancelPending}
          onConfirm={() => undefined}
          onOpenChange={() => undefined}
          open
          pendingMessage="请把主角的公开代价改得更具体。"
          receipt={receipt()}
        />,
      )
      await Promise.resolve()
    })

    expect(document.body.textContent).toContain(
      "请把主角的公开代价改得更具体。",
    )
    expect(document.body.textContent).toContain("当前转折")
    const abandon = Array.from(
      document.body.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.textContent?.includes("放弃本次"))
    expect(abandon).toBeDefined()
    act(() => abandon?.click())
    expect(onCancelPending).toHaveBeenCalledOnce()

    act(() => root.unmount())
    document.body
      .querySelectorAll("[data-radix-portal]")
      .forEach((node) => node.remove())
  })

  it("lets the author select distinct context systems and project knowledge sources", async () => {
    const container = document.createElement("div")
    document.body.append(container)
    const root = createRoot(container)
    const onKnowledgeToggle = vi.fn()
    const onOptionChange = vi.fn()

    await act(async () => {
      root.render(
        <ContextSourcePicker
          disabled={false}
          knowledgeDocuments={[
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
          ]}
          onKnowledgeToggle={onKnowledgeToggle}
          onOpenKnowledgeManager={() => undefined}
          onOptionChange={onOptionChange}
          policy={contextPolicy()}
        />,
      )
      await Promise.resolve()
    })
    const trigger = document.body.querySelector<HTMLButtonElement>(
      '[aria-label="选择本轮上下文"]',
    )
    await act(async () => {
      trigger?.click()
      await Promise.resolve()
    })

    const canonToggle = Array.from(document.body.querySelectorAll("label"))
      .find((label) => label.textContent?.includes("相关 Canon / Wiki"))
      ?.querySelector<HTMLInputElement>("input")
    act(() => canonToggle?.click())
    expect(onOptionChange).toHaveBeenCalledWith("include_canon_wiki", false)

    const knowledge = Array.from(
      document.body.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.textContent?.includes("母带保管规范"))
    act(() => knowledge?.click())
    expect(onKnowledgeToggle).toHaveBeenCalledWith("kb-1")

    act(() => root.unmount())
    container.remove()
    document.body
      .querySelectorAll("[data-radix-portal]")
      .forEach((node) => node.remove())
  })
})

function patch(
  status: ArtifactPatchCandidate["status"],
): ArtifactPatchCandidate {
  return {
    patch_id: "patch-1",
    thread_id: "thread-1",
    turn_id: "turn-1",
    run_id: "run-1",
    creation_route_id: "short_novel",
    route_revision: "r3",
    stage_id: "story_map",
    artifact_kind: "story_map",
    source_artifact_ref: "story-map-v1",
    source_signature: "a".repeat(64),
    effective_payload_digest: "d".repeat(64),
    unit_ref: "turn-1",
    operations: [
      {
        operation: "replace_text",
        field_path: "anchors.0.consequence_or_open_effect",
        before_hash: "b".repeat(64),
        selection_anchor_id: "anchor-1",
        replacement: "主角公开证据并承担代价",
        rationale: "把抽象进展改为可见行动。",
      },
    ],
    context_receipt_ref: "receipt-1",
    provider_operation_ref: "operation-1",
    status,
    created_at: "2026-08-21T00:00:00Z",
    updated_at: "2026-08-21T00:00:00Z",
  }
}

function turn(
  status: CollaborationTurn["status"],
  code = "",
): CollaborationTurn {
  return {
    turn_id: "turn-1",
    client_turn_id: "client-turn-1",
    thread_id: "thread-1",
    run_id: "run-1",
    mode: "discuss",
    status,
    user_message_ref: "message-user-turn-1",
    assistant_message_ref: "",
    context_receipt_ref: "receipt-1",
    context_preview_signature: "a".repeat(64),
    provider_operation_ref: "",
    patch_candidate_ref: "",
    selection_anchor: null,
    error: code ? { code, message: code } : null,
    created_at: "2026-08-21T00:00:00Z",
    updated_at: "2026-08-21T00:00:00Z",
  }
}

function receipt(): CollaborationContextReceipt {
  return {
    receipt_id: "receipt-1",
    thread_id: "thread-1",
    turn_id: "turn-1",
    run_id: "run-1",
    creation_route_id: "short_novel",
    route_revision: "r3",
    stage_id: "story_map",
    artifact_kind: "story_map",
    source_artifact_ref: "story-map-v1",
    source_signature: "a".repeat(64),
    effective_payload_digest: "e".repeat(64),
    sources: [
      {
        category: "artifact",
        source_ref: "story-map-v1",
        scope_ref: "turn-1",
        source_version: "v1",
        reason: "当前讨论范围",
        char_count: 120,
        token_estimate: 60,
        disposition: "required",
        label: "当前转折",
      },
    ],
    history_message_refs: [],
    budget_chars: 24_000,
    used_chars: 120,
    token_estimate: 60,
    provider_profile_id: "provider-1",
    model: "model-1",
    receipt_hash: "c".repeat(64),
    created_at: "2026-08-21T00:00:00Z",
  }
}

function contextPolicy(): CollaborationContextPolicy {
  return {
    policy_id: "collaboration-default-v1",
    version: 1,
    max_input_chars: 24_000,
    max_history_turns: 8,
    include_author_preferences: true,
    include_craft_mechanisms: true,
    include_knowledge: true,
    include_canon_wiki: true,
    include_foreshadow: true,
    author_preferences: "",
    craft_mechanisms: [],
    source_pack_refs: [],
  }
}
