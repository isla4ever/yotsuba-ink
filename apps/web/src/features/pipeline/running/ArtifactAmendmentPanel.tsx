import { useEffect, useMemo, useRef } from "react"
import type { RefObject } from "react"
import { createPortal } from "react-dom"
import {
  ArrowLeft,
  Check,
  FileDiff,
  LoaderCircle,
  ScanSearch,
  X,
} from "lucide-react"
import type { Phase32RouteStageManifest } from "../contracts/run"
import type { ArtifactAmendmentController } from "../state/useArtifactAmendment"
import { AmendmentSuccessorView } from "./AmendmentSuccessorView"
import { ArtifactImpactSummary } from "./ArtifactImpactSummary"

export function ArtifactAmendmentPanel({
  flow,
  manifest,
  sourceRunId,
  onEnterSuccessor,
}: {
  flow: ArtifactAmendmentController
  manifest: Phase32RouteStageManifest[]
  sourceRunId: string
  onEnterSuccessor: () => Promise<void> | void
}) {
  const reviewButtonRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const open = !["idle", "editing"].includes(flow.phase)
  const labels = useMemo(
    () => new Map(manifest.map((stage) => [stage.stage_id, stage.label])),
    [manifest],
  )
  const label = (stageId: string) => labels.get(stageId) ?? stageId

  useDialogFocus(dialogRef, open, () => {
    if (["review", "impact"].includes(flow.phase)) flow.returnToEdit()
  })

  useEffect(() => {
    if (flow.phase === "editing") reviewButtonRef.current?.focus()
  }, [flow.phase])

  if (flow.phase === "idle") return null
  if (flow.phase === "editing") {
    return (
      <div className="artifact-amendment-inline" role="status">
        <FileDiff size={12} />
        <span>正式修订副本</span>
        <button
          className="btn btn-ghost text-xs"
          onClick={flow.cancel}
          type="button"
        >
          取消
        </button>
        <button
          className="btn btn-action text-xs"
          disabled={!flow.hasChanges}
          onClick={flow.openReview}
          ref={reviewButtonRef}
          type="button"
        >
          <ScanSearch size={12} /> 预览影响
        </button>
      </div>
    )
  }

  const canClose = ["review", "impact"].includes(flow.phase)
  const previewBusy = flow.phase === "previewing"
  const applyBusy = flow.phase === "applying"
  const successorPhase = [
    "restoring",
    "applied",
    "branching",
    "successor",
  ].includes(flow.phase)

  return createPortal(
    <div className="artifact-amendment-overlay" role="presentation">
      <div
        aria-labelledby="artifact-amendment-title"
        aria-modal="true"
        className={`artifact-amendment-dialog ${
          successorPhase ? "is-successor" : ""
        }`}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header>
          <div>
            <span>FORMAL AMENDMENT</span>
            <h1 id="artifact-amendment-title">
              {successorPhase
                ? "修订分支"
                : flow.phase === "review" || previewBusy
                  ? "提交修订草案"
                  : "确定性影响分析"}
            </h1>
          </div>
          {canClose ? (
            <button
              aria-label="返回修订编辑"
              className="amendment-dialog-close"
              onClick={flow.returnToEdit}
              title="返回修订编辑"
              type="button"
            >
              <X size={15} />
            </button>
          ) : null}
        </header>

        <div className="artifact-amendment-dialog-body">
          {successorPhase ? (
            <AmendmentSuccessorView
              flow={flow}
              onEnterSuccessor={onEnterSuccessor}
              sourceRunId={sourceRunId}
              stageLabel={label}
            />
          ) : flow.phase === "review" || previewBusy ? (
            <div className="amendment-review-step">
              <div className="amendment-review-source">
                <FileDiff size={15} />
                <div>
                  <strong>
                    {label(flow.amendment?.source_stage_id ?? "") ||
                      "当前规划阶段"}
                  </strong>
                  <span>
                    修改副本会在服务端校验后生成不可变 amendment 与
                    ImpactAnalysis。
                  </span>
                </div>
              </div>
              <label>
                <span>
                  本次修订说明 <em>可选</em>
                </span>
                <textarea
                  autoFocus
                  disabled={previewBusy}
                  maxLength={4000}
                  onChange={(event) => flow.setAuthorNote(event.target.value)}
                  placeholder="例如：收紧中段承诺，让后续场景只保留一条调查主线。"
                  rows={4}
                  value={flow.authorNote}
                />
              </label>
              <div className="amendment-review-rule">
                不会调用 Provider。系统只校验 Artifact
                合同、稳定引用和现有下游依赖。
              </div>
              {flow.error ? (
                <div className="amendment-dialog-error" role="alert">
                  {flow.error}
                </div>
              ) : null}
              <footer>
                <button
                  className="btn btn-secondary text-xs"
                  disabled={previewBusy}
                  onClick={flow.returnToEdit}
                  type="button"
                >
                  <ArrowLeft size={12} /> 返回编辑
                </button>
                <button
                  className="btn btn-primary text-xs"
                  disabled={previewBusy}
                  onClick={() => void flow.preview()}
                  type="button"
                >
                  {previewBusy ? (
                    <LoaderCircle className="is-spinning" size={13} />
                  ) : (
                    <ScanSearch size={13} />
                  )}
                  {previewBusy ? "正在分析" : "生成影响分析"}
                </button>
              </footer>
            </div>
          ) : flow.impact ? (
            <>
              <ArtifactImpactSummary
                impact={flow.impact}
                manifest={manifest}
                onScopeChange={flow.setScope}
                scope={flow.scope}
              />
              {flow.error ? (
                <div className="amendment-dialog-error" role="alert">
                  {flow.error}
                </div>
              ) : null}
              <footer className="amendment-impact-actions">
                <button
                  className="btn btn-secondary text-xs"
                  disabled={applyBusy}
                  onClick={flow.returnToEdit}
                  type="button"
                >
                  <ArrowLeft size={12} /> 调整修订
                </button>
                <button
                  className="btn btn-primary text-xs"
                  disabled={
                    applyBusy || Boolean(flow.impact.blocked_references.length)
                  }
                  onClick={() => void flow.apply()}
                  type="button"
                >
                  {applyBusy ? (
                    <LoaderCircle className="is-spinning" size={13} />
                  ) : (
                    <Check size={13} />
                  )}
                  {applyBusy ? "正在应用" : "应用修订并冻结旧 Run"}
                </button>
              </footer>
            </>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  )
}

function useDialogFocus(
  ref: RefObject<HTMLDivElement | null>,
  open: boolean,
  onEscape: () => void,
) {
  const escapeRef = useRef(onEscape)
  escapeRef.current = onEscape

  useEffect(() => {
    if (!open || !ref.current) return undefined
    const dialog = ref.current
    const returnTarget = document.activeElement as HTMLElement | null
    const focusable = () =>
      Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not(:disabled), textarea:not(:disabled), input:not(:disabled), [tabindex="0"]',
        ),
      )
    ;(focusable()[0] ?? dialog).focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault()
        escapeRef.current()
        return
      }
      if (event.key !== "Tab") return
      const items = focusable()
      if (!items.length) {
        event.preventDefault()
        dialog.focus()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    dialog.addEventListener("keydown", handleKeyDown)
    return () => {
      dialog.removeEventListener("keydown", handleKeyDown)
      returnTarget?.focus()
    }
  }, [open, ref])
}
