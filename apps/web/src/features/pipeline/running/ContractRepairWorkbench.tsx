import { useMemo } from "react"
import {
  AlertTriangle,
  ArrowLeft,
  FileWarning,
  RotateCcw,
  ShieldCheck,
  Wrench,
} from "lucide-react"
import "../../../styles/contract-repair.css"
import type { Phase32RunEnvelope } from "../contracts/run"
import {
  parsePhase32RollingDetail,
  type RollingDetailReferenceContext,
} from "../lib/phase32RollingDetail"
import { useContractRepair } from "../state/useContractRepair"
import { BookLoader } from "../layout/BookLoader"
import { RollingDetailArtifactEditor } from "./RollingDetailArtifactEditor"

type RepairFinding = {
  code: string
  message: string
}

export function ContractRepairWorkbench({
  onRestored,
  referenceContext,
  referenceContextError = "",
  run,
}: {
  onRestored: (run: Phase32RunEnvelope) => Promise<unknown> | unknown
  referenceContext: RollingDetailReferenceContext
  referenceContextError?: string
  run: Phase32RunEnvelope
}) {
  const flow = useContractRepair({ enabled: true, onRestored, run })
  const parsed = useMemo(
    () => parsePhase32RollingDetail(flow.payload),
    [flow.payload],
  )
  const providerOperations = run.read_model.provider_usage.provider_operations
  const failure = run.read_model.failure

  if (flow.phase === "loading") {
    return (
      <BookLoader
        detail="核对当前失败阶段、最新 Provider 回执与可修复边界"
        label="正在读取合同隔离稿"
        variant="panel"
      />
    )
  }

  if (flow.phase === "editing" || flow.phase === "submitting") {
    const submitting = flow.phase === "submitting"
    return (
      <div className="phase32-contract-repair phase32-detail-page page-in">
        <header className="phase32-contract-repair-toolbar">
          <div>
            <Wrench size={13} />
            <span>隔离稿修复</span>
            <small>只产生候选，不自动接受</small>
          </div>
          <div>
            <button
              className="btn btn-ghost text-xs"
              disabled={submitting}
              onClick={flow.cancel}
              type="button"
            >
              <ArrowLeft size={12} /> 返回失败摘要
            </button>
            <button
              className="btn btn-primary text-xs"
              disabled={
                submitting ||
                !flow.hasChanges ||
                !parsed.artifact ||
                Boolean(parsed.error)
              }
              onClick={() => void flow.submit()}
              type="button"
            >
              <ShieldCheck size={12} />
              {submitting ? "正在重新校验…" : "重新校验并恢复候选"}
            </button>
          </div>
        </header>

        <RepairFindingBand
          error={flow.error || parsed.error || referenceContextError}
          findings={flow.quarantine?.findings ?? []}
          providerOperations={providerOperations}
        />

        {parsed.artifact && flow.quarantine ? (
          <RollingDetailArtifactEditor
            allowCastScopeEditing={!referenceContextError}
            artifact={parsed.artifact}
            artifactRef={flow.quarantine.provider_receipt_ref}
            editable={!submitting}
            onChange={flow.change}
            referenceContext={referenceContext}
            revisionLabel={`隔离回执 · ${shortRef(flow.quarantine.provider_receipt_ref)}`}
          />
        ) : null}
      </div>
    )
  }

  const eligible = Boolean(flow.quarantine?.eligible)
  return (
    <div className="phase32-contract-repair-summary page-in">
      <section aria-labelledby="contract-repair-title">
        <header>
          <div className="phase32-contract-repair-mark">
            <FileWarning size={21} />
          </div>
          <div>
            <span>PROVIDER CONTRACT QUARANTINE</span>
            <h1 id="contract-repair-title">滚动细纲未进入候选库</h1>
          </div>
        </header>

        <p className="phase32-contract-repair-lead">
          {failure?.message || "Provider 返回未通过阶段引用合同。"}
        </p>

        <div className="phase32-contract-repair-finding-list">
          {(flow.quarantine?.findings ?? []).map((finding) => (
            <div key={`${finding.code}:${finding.message}`}>
              <AlertTriangle size={13} />
              <span>
                <small>{finding.code}</small>
                <strong>{finding.message}</strong>
              </span>
            </div>
          ))}
          {flow.error ? (
            <div role="alert">
              <AlertTriangle size={13} />
              <span>
                <small>quarantine_unavailable</small>
                <strong>{flow.error}</strong>
              </span>
            </div>
          ) : null}
          {referenceContextError ? (
            <div role="alert">
              <AlertTriangle size={13} />
              <span>
                <small>upstream_reference_context_unavailable</small>
                <strong>{referenceContextError}</strong>
              </span>
            </div>
          ) : null}
        </div>

        <footer>
          <div>
            <span>Provider 调用</span>
            <strong>{providerOperations}</strong>
            <small>隔离修复不会增加该计数</small>
          </div>
          <div>
            <span>原始回执</span>
            <code title={flow.quarantine?.provider_receipt_ref}>
              {shortRef(flow.quarantine?.provider_receipt_ref ?? "")}
            </code>
            <small>原回执保持不可变</small>
          </div>
          <button
            className="btn btn-primary text-xs"
            disabled={!eligible}
            onClick={flow.begin}
            type="button"
          >
            <RotateCcw size={12} />
            {eligible ? "载入隔离稿" : "此返回不可人工修复"}
          </button>
        </footer>
      </section>
    </div>
  )
}

function RepairFindingBand({
  error,
  findings,
  providerOperations,
}: {
  error: string
  findings: RepairFinding[]
  providerOperations: number
}) {
  return (
    <section
      className={`phase32-contract-repair-band ${error ? "has-error" : ""}`}
      aria-live="polite"
    >
      <div>
        <AlertTriangle size={12} />
        <span>
          {error || findings.map((finding) => finding.message).join("；")}
        </span>
      </div>
      <small>
        Provider 调用保持 {providerOperations} · 修复后回到人工候选门
      </small>
    </section>
  )
}

function shortRef(value: string) {
  if (!value) return "—"
  return value.length > 32 ? `${value.slice(0, 18)}…${value.slice(-8)}` : value
}
