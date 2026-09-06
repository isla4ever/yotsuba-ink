import {
  ArrowRight,
  CheckCircle2,
  GitBranch,
  History,
  LoaderCircle,
  RotateCcw,
} from "lucide-react"
import { useState } from "react"
import type { ArtifactAmendmentController } from "../state/useArtifactAmendment"

export function AmendmentSuccessorView({
  flow,
  stageLabel,
  sourceRunId,
  onEnterSuccessor,
}: {
  flow: ArtifactAmendmentController
  stageLabel: (stageId: string) => string
  sourceRunId: string
  onEnterSuccessor: () => Promise<void> | void
}) {
  const [entering, setEntering] = useState(false)
  const [enterError, setEnterError] = useState("")
  if (flow.phase === "restoring") {
    return (
      <div className="amendment-successor-state" aria-live="polite">
        <LoaderCircle className="is-spinning" size={20} />
        <h2>正在恢复修订分支</h2>
        <p>从服务端读取 ImpactAnalysis、apply receipt 与已创建的 successor。</p>
        {flow.error ? (
          <>
            <div className="amendment-dialog-error" role="alert">
              {flow.error}
            </div>
            <button
              className="btn btn-secondary text-xs"
              onClick={flow.retryRestore}
              type="button"
            >
              <RotateCcw size={12} /> 重试恢复
            </button>
          </>
        ) : null}
      </div>
    )
  }

  if (flow.phase === "successor" && flow.branchReceipt && flow.targetRun) {
    const inherited = Object.keys(flow.branchReceipt.imported_artifact_refs)
    return (
      <div className="amendment-successor-state is-ready">
        <CheckCircle2 size={22} />
        <span>SUCCESSOR READY</span>
        <h2>新的创作分支已经就绪</h2>
        <p>
          新 Run 从{" "}
          <strong>{stageLabel(flow.branchReceipt.frontier_stage_id)}</strong>{" "}
          继续，原 Run 保持完整历史，不复制旧正文或旧 checkpoint。
        </p>
        <div className="amendment-run-lineage" aria-label="Run 分支关系">
          <div>
            <History size={13} />
            <span>历史 Run</span>
            <code>{shortRef(sourceRunId)}</code>
          </div>
          <ArrowRight size={15} />
          <div className="is-target">
            <GitBranch size={13} />
            <span>Successor</span>
            <code>{shortRef(flow.branchReceipt.target_run_id)}</code>
          </div>
        </div>
        <div className="amendment-inherited-stages">
          <span>继承的已提交规划</span>
          <div>
            {inherited.map((stageId) => (
              <em key={stageId}>{stageLabel(stageId)}</em>
            ))}
          </div>
        </div>
        {enterError ? (
          <div className="amendment-dialog-error" role="alert">
            {enterError}
          </div>
        ) : null}
        <button
          className="btn btn-primary"
          disabled={entering}
          onClick={() => {
            setEntering(true)
            setEnterError("")
            void Promise.resolve(onEnterSuccessor())
              .catch((reason) =>
                setEnterError(
                  reason instanceof Error
                    ? reason.message
                    : "无法进入 successor Run",
                ),
              )
              .finally(() => setEntering(false))
          }}
          type="button"
        >
          {entering ? <LoaderCircle className="is-spinning" size={13} /> : null}
          {entering ? "正在切换" : "进入新 Run"} <ArrowRight size={13} />
        </button>
        {flow.error ? (
          <div className="amendment-dialog-error" role="alert">
            {flow.error}
          </div>
        ) : null}
      </div>
    )
  }

  const busy = flow.phase === "branching"
  return (
    <div className="amendment-successor-state">
      <GitBranch size={22} />
      <span>ORIGINAL RUN · READ ONLY</span>
      <h2>修订已应用，等待创建新 Run</h2>
      <p>
        旧 Run 的 accepted history 已冻结。系统将从最早 stale frontier 创建新的
        Run、thread 与 checkpoint。
      </p>
      <div className="amendment-stale-strip">
        {flow.impact?.[
          flow.scope === "affected_only"
            ? "affected_only_scope"
            : "restart_from_stage_scope"
        ].map((stageId) => <span key={stageId}>{stageLabel(stageId)}</span>)}
      </div>
      <dl className="amendment-receipt-facts">
        <div>
          <dt>Apply receipt</dt>
          <dd>{shortRef(flow.applyReceipt?.receipt_id ?? "")}</dd>
        </div>
        <div>
          <dt>Domain revision</dt>
          <dd>{flow.applyReceipt?.domain_revision_after ?? "-"}</dd>
        </div>
      </dl>
      {flow.error ? (
        <div className="amendment-dialog-error" role="alert">
          {flow.error}
        </div>
      ) : null}
      <button
        className="btn btn-primary"
        disabled={busy || !flow.applyReceipt}
        onClick={() => void flow.branch()}
        type="button"
      >
        {busy ? (
          <LoaderCircle className="is-spinning" size={13} />
        ) : (
          <GitBranch size={13} />
        )}
        {busy ? "正在创建 successor" : "创建 successor Run"}
      </button>
    </div>
  )
}

function shortRef(value: string) {
  if (!value) return "-"
  return value.length > 34 ? `${value.slice(0, 20)}…${value.slice(-9)}` : value
}
