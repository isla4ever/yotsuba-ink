import { CircleStop, Lock, Sparkles } from "lucide-react"
import { useState } from "react"
import type { StageDecision } from "../lib/stageDecision"
import { resolveRunDecision } from "../services/runApi"

type DialogKind = "regenerate" | "cancel" | null
type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

type Props = {
  acceptLabel: string
  artifact: Record<string, unknown> | null
  decision: StageDecision
  disabled?: boolean
  draftStatus: string
  onResolved: () => Promise<unknown>
  regenerateDescription: string
  regeneratePlaceholder: string
  regenerateTitle: string
  runId: string
}

export function StageCandidateActions({
  acceptLabel,
  artifact,
  decision,
  disabled = false,
  draftStatus,
  onResolved,
  regenerateDescription,
  regeneratePlaceholder,
  regenerateTitle,
  runId,
}: Props) {
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] = useState<ActionState>("idle")
  const [error, setError] = useState("")
  const busy = actionState !== "idle"

  const submit = async (action: "accept" | "regenerate" | "cancel") => {
    if (busy || disabled) return
    if (action === "accept" && !artifact) {
      setError("当前候选稿尚未通过阶段合同校验")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setError("请先填写本次换稿方向")
      return
    }
    setActionState(
      action === "accept"
        ? "accepting"
        : action === "regenerate"
          ? "regenerating"
          : "cancelling",
    )
    setError("")
    try {
      await resolveRunDecision(
        runId,
        decision.decisionId,
        action,
        decision.domainRevision,
        action === "accept" ? artifact ?? undefined : undefined,
        action === "regenerate" ? direction : undefined,
      )
      setDialog(null)
      setDirection("")
      await onResolved()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "阶段决策提交失败")
    } finally {
      setActionState("idle")
    }
  }

  return (
    <>
      <div className="stage-candidate-actions">
        <span className={`stage-draft-state ${draftStatus}`}>
          {draftStatusLabel(draftStatus)}
        </span>
        {decision.allowedActions.includes("regenerate") && (
          <button
            type="button"
            className="btn btn-secondary text-xs"
            disabled={busy}
            onClick={() => {
              setError("")
              setDialog("regenerate")
            }}
          >
            <Sparkles size={12} />
            定向换稿
          </button>
        )}
        {decision.allowedActions.includes("cancel") && (
          <button
            type="button"
            className="btn btn-ghost text-risk text-xs"
            disabled={busy}
            onClick={() => {
              setError("")
              setDialog("cancel")
            }}
          >
            <CircleStop size={12} />
            取消
          </button>
        )}
        {decision.allowedActions.includes("accept") && (
          <button
            type="button"
            className="btn btn-primary text-xs"
            disabled={busy || disabled || !artifact}
            onClick={() => void submit("accept")}
          >
            <Lock size={12} />
            {actionState === "accepting" ? "正在定稿…" : acceptLabel}
          </button>
        )}
        {error && !dialog && (
          <span className="stage-candidate-error" role="alert" title={error}>
            {error}
          </span>
        )}
      </div>

      {dialog && (
        <div
          className="stage-candidate-dialog-backdrop"
          role="presentation"
          onMouseDown={() => !busy && setDialog(null)}
        >
          <section
            className="stage-candidate-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="stage-candidate-dialog-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <span className="stage-candidate-dialog-kicker">
              {dialog === "cancel" ? "停止执行" : "同一冻结合同"}
            </span>
            <h2 id="stage-candidate-dialog-title">
              {dialog === "cancel" ? "取消当前创作 Run？" : regenerateTitle}
            </h2>
            <p>
              {dialog === "cancel"
                ? "取消只会终止当前 Run；已经定稿的 Artifact 和历史证据不会被删除或改写。"
                : regenerateDescription}
            </p>
            {dialog === "regenerate" && (
              <label>
                <span>修订方向</span>
                <textarea
                  className="input"
                  rows={4}
                  value={direction}
                  onChange={(event) => setDirection(event.target.value)}
                  placeholder={regeneratePlaceholder}
                  autoFocus
                />
              </label>
            )}
            {error && (
              <p className="stage-candidate-dialog-error" role="alert">
                {error}
              </p>
            )}
            <footer>
              <button
                type="button"
                className="btn btn-secondary text-xs"
                disabled={busy}
                onClick={() => setDialog(null)}
              >
                返回
              </button>
              <button
                type="button"
                className={`btn text-xs ${dialog === "cancel" ? "btn-danger" : "btn-primary"}`}
                disabled={busy || (dialog === "regenerate" && !direction.trim())}
                onClick={() => void submit(dialog === "cancel" ? "cancel" : "regenerate")}
              >
                {busy
                  ? "正在提交…"
                  : dialog === "cancel"
                    ? "确认取消"
                    : "开始换稿"}
              </button>
            </footer>
          </section>
        </div>
      )}
    </>
  )
}

function draftStatusLabel(status: string) {
  return (
    ({
      clean: "原始候选",
      dirty: "尚未保存",
      error: "草稿异常",
      loading: "读取草稿",
      saved: "草稿已保存",
      saving: "保存中",
    } as Record<string, string>)[status] ?? "候选稿"
  )
}
