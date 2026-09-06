import {
  Archive,
  CheckCircle2,
  CircleAlert,
  RefreshCw,
  ShieldAlert,
} from "lucide-react"
import type { ReactNode } from "react"
import type {
  AmendmentApplyScope,
  AmendmentImpactTarget,
  ArtifactImpactAnalysis,
} from "../contracts/artifactAmendment"
import type { Phase32RouteStageManifest } from "../contracts/run"

export function ArtifactImpactSummary({
  impact,
  manifest,
  scope,
  onScopeChange,
}: {
  impact: ArtifactImpactAnalysis
  manifest: Phase32RouteStageManifest[]
  scope: AmendmentApplyScope
  onScopeChange: (scope: AmendmentApplyScope) => void
}) {
  const labels = new Map(manifest.map((stage) => [stage.stage_id, stage.label]))
  const affected = impact.affected_only_scope
  const restarted = impact.restart_from_stage_scope

  return (
    <div className="amendment-impact-summary">
      {impact.blocked_references.length ? (
        <section className="amendment-impact-blocked" role="alert">
          <ShieldAlert size={16} />
          <div>
            <strong>存在不可安全改写的稳定引用</strong>
            <p>
              这些引用已经进入已提交或已接受内容。请返回编辑并保留对应
              ref，当前修订不能应用。
            </p>
            <ul>
              {impact.blocked_references.map((item) => (
                <li key={`${item.reference}:${item.unit_ref}`}>
                  <code>{item.reference}</code>
                  <span>
                    {labels.get(item.referenced_stage_id) ??
                      item.referenced_stage_id}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <div className="amendment-impact-ledgers">
        <ImpactLedger
          icon={<CheckCircle2 size={14} />}
          title="保持有效"
          count={impact.preserved.length}
          targets={impact.preserved}
          labels={labels}
          tone="preserved"
          empty="没有可直接保留的下游产物"
        />
        <ImpactLedger
          icon={<RefreshCw size={14} />}
          title="需要重算"
          count={impact.stale.length}
          targets={impact.stale}
          labels={labels}
          tone="stale"
          empty="没有被当前变更影响的下游产物"
        />
        <ImpactLedger
          icon={<Archive size={14} />}
          title="历史冻结"
          count={impact.historical_frozen.length}
          targets={impact.historical_frozen}
          labels={labels}
          tone="historical"
          empty="没有需要只读保留的已接受历史"
        />
      </div>

      <fieldset className="amendment-scope-picker">
        <legend>Successor Run 重算边界</legend>
        <label className={scope === "affected_only" ? "is-selected" : ""}>
          <input
            checked={scope === "affected_only"}
            name="amendment-scope"
            onChange={() => onScopeChange("affected_only")}
            type="radio"
          />
          <span>
            <strong>只重算受影响阶段</strong>
            <small>{scopeLabel(affected, labels)}</small>
          </span>
          <em>{affected.length}</em>
        </label>
        <label className={scope === "restart_from_stage" ? "is-selected" : ""}>
          <input
            checked={scope === "restart_from_stage"}
            name="amendment-scope"
            onChange={() => onScopeChange("restart_from_stage")}
            type="radio"
          />
          <span>
            <strong>从阶段边界重新执行</strong>
            <small>{scopeLabel(restarted, labels)}</small>
          </span>
          <em>{restarted.length}</em>
        </label>
      </fieldset>

      <div className="amendment-impact-note">
        <CircleAlert size={13} />
        <span>
          应用后原 Run 永久转为只读历史；正式继续会创建新的 Run、thread 与
          checkpoint。
        </span>
      </div>
    </div>
  )
}

function ImpactLedger({
  icon,
  title,
  count,
  targets,
  labels,
  tone,
  empty,
}: {
  icon: ReactNode
  title: string
  count: number
  targets: AmendmentImpactTarget[]
  labels: Map<string, string>
  tone: "preserved" | "stale" | "historical"
  empty: string
}) {
  return (
    <section className={`amendment-impact-ledger is-${tone}`}>
      <header>
        {icon}
        <strong>{title}</strong>
        <span>{count}</span>
      </header>
      {targets.length ? (
        <ol>
          {targets.map((target, index) => (
            <li
              key={`${target.stage_id}:${target.artifact_ref}:${target.unit_ref}:${index}`}
            >
              <div>
                <strong>
                  {labels.get(target.stage_id) ?? target.stage_id}
                </strong>
                {target.unit_ref ? <code>{target.unit_ref}</code> : null}
              </div>
              <p>{target.reason}</p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="amendment-impact-empty">{empty}</p>
      )}
    </section>
  )
}

function scopeLabel(stageIds: string[], labels: Map<string, string>) {
  if (!stageIds.length) return "没有可执行的下游边界"
  return stageIds.map((stageId) => labels.get(stageId) ?? stageId).join(" → ")
}
