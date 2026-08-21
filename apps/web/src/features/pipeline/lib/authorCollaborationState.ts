import type { AppendMessage } from "@assistant-ui/react"
import type {
  CollaborationContextPreviewInput,
  CollaborationContextReceipt,
  CollaborationStageId,
  CollaborationThread,
} from "../contracts/authorCollaboration"
import { AuthorCollaborationApiError } from "../services/authorCollaborationApi"

export type PendingCollaborationSubmission = {
  input: CollaborationContextPreviewInput
  receipt: CollaborationContextReceipt
  threadId: string
}

export function collaborationThreadMatchesScope(
  thread: CollaborationThread,
  stageId: CollaborationStageId,
  sourceRef: string,
  unitRef: string,
) {
  return thread.status === "active"
    && thread.stage_id === stageId
    && (!sourceRef || thread.scope.source_ref === sourceRef)
    && thread.scope.unit_ref === unitRef
}

export function appendMessageText(message: AppendMessage) {
  return message.content
    .filter((part): part is Extract<(typeof message.content)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim()
}

export function collaborationErrorMessage(error: unknown) {
  if (error instanceof AuthorCollaborationApiError) {
    const labels: Record<string, string> = {
      author_collaboration_unavailable: "作者协作仅在精细模式的当前运行中可用。",
      collaboration_source_stale: "当前产物已更新，请新建对话后继续。",
      context_budget_exceeded: "本轮上下文超过预算，请减少引用或缩短问题。",
      collaboration_thread_busy: "请先停止当前生成，再归档或删除这段对话。",
      patch_stale: "原文已经变化，这份改稿不能再应用。",
      patch_writeback_unavailable: "当前正式版本需要通过版本修订流程写回，不能原地覆盖。",
      turn_replay_conflict: "这次发送与已记录请求冲突，请新建一轮。",
    }
    return labels[error.code] ?? error.message
  }
  return error instanceof Error ? error.message : "作者协作请求失败"
}
