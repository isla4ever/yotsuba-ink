import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDollarSign,
  Cpu,
  DatabaseZap,
  FileCheck2,
  ScrollText,
  ShieldAlert,
  X,
} from "lucide-react"
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react"
import type { Phase32RunEnvelope, Phase32RunEvent } from "../../contracts/run"
import { eventCategory } from "../../lib/phase32RunMonitor"
import type { RunConnectionState } from "../../state/useActiveRun"
import {
  formatPhase32RunEventClock,
  phase32RunEventDetail,
  phase32RunEventLabel,
} from "./phase32RunMonitorPresentation"

type Props = {
  connection: RunConnectionState
  events: Phase32RunEvent[]
  onClose: () => void
  open: boolean
  returnFocusRef: RefObject<HTMLButtonElement | null>
  run: Phase32RunEnvelope
}

type InspectorView = "status" | "logs"

export function Phase32RunMonitorInspector({
  connection,
  events,
  onClose,
  open,
  returnFocusRef,
  run,
}: Props) {
  const [view, setView] = useState<InspectorView>("status")
  const closeRef = useRef<HTMLButtonElement>(null)
  const inspectorRef = useRef<HTMLElement>(null)
  const { read_model: readModel, summary } = run
  const usage = readModel.provider_usage
  const visibleEvents = useMemo(() => events.slice(-200).reverse(), [events])
  const lastSequence = events.at(-1)?.sequence ?? 0
  const categoryCounts = useMemo(
    () =>
      events.reduce<Record<string, number>>((counts, event) => {
        const category = eventCategory(event)
        counts[category] = (counts[category] ?? 0) + 1
        return counts
      }, {}),
    [events],
  )

  const requestClose = () => {
    returnFocusRef.current?.focus({ preventScroll: true })
    onClose()
  }

  useEffect(() => {
    if (!open) return undefined
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [onClose, open, returnFocusRef])

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined
    const drawerQuery = window.matchMedia("(max-width: 1279px)")
    const restoreFocusAtDrawerBreakpoint = (event: MediaQueryListEvent) => {
      if (!event.matches || open) return
      const activeElement = document.activeElement
      if (
        activeElement instanceof HTMLElement &&
        inspectorRef.current?.contains(activeElement)
      ) {
        returnFocusRef.current?.focus({ preventScroll: true })
      }
    }
    drawerQuery.addEventListener("change", restoreFocusAtDrawerBreakpoint)
    return () =>
      drawerQuery.removeEventListener("change", restoreFocusAtDrawerBreakpoint)
  }, [open, returnFocusRef])

  return (
    <Fragment>
      <button
        aria-label="关闭运行检查器"
        className={`phase32-monitor-inspector-backdrop ${
          open ? "is-open" : ""
        }`}
        onClick={requestClose}
        tabIndex={open ? 0 : -1}
        type="button"
      />
      <aside
        aria-label="运行状态与日志"
        className={`phase32-monitor-inspector ${open ? "is-open" : ""}`}
        ref={inspectorRef}
      >
        <header className="phase32-monitor-inspector-heading">
          <div>
            <Activity size={13} />
            <span>运行检查器</span>
          </div>
          <button
            aria-label="关闭运行检查器"
            className="phase32-monitor-inspector-close"
            onClick={requestClose}
            ref={closeRef}
            type="button"
          >
            <X size={14} />
          </button>
        </header>

        <div className="phase32-monitor-inspector-tabs" role="tablist">
          <button
            aria-selected={view === "status"}
            className={view === "status" ? "is-active" : ""}
            onClick={() => setView("status")}
            role="tab"
            type="button"
          >
            运行状态
          </button>
          <button
            aria-selected={view === "logs"}
            className={view === "logs" ? "is-active" : ""}
            onClick={() => setView("logs")}
            role="tab"
            type="button"
          >
            完整日志
            <span>{events.length}</span>
          </button>
        </div>

        <div className="phase32-monitor-inspector-scroll">
          {view === "status" ? (
            <>
              {readModel.failure ? (
                <InspectorSection
                  icon={<ShieldAlert size={13} />}
                  tone="risk"
                  title="当前异常"
                >
                  <p className="phase32-monitor-failure-copy">
                    {readModel.failure.message}
                  </p>
                  <InspectorRow
                    label="错误码"
                    value={readModel.failure.code}
                    mono
                  />
                  <InspectorRow
                    label="定位"
                    value={[
                      readModel.failure.stage_id,
                      readModel.failure.unit_ref,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                    mono
                  />
                  <InspectorRow
                    label="可重试"
                    value={readModel.failure.retryable ? "是" : "否"}
                  />
                </InspectorSection>
              ) : null}

              <InspectorSection icon={<Activity size={13} />} title="运行健康">
                <InspectorRow
                  label="连接"
                  value={connectionLabel(connection)}
                />
                <InspectorRow
                  label="Run 状态"
                  value={runStatusLabel(readModel.status)}
                />
                <InspectorRow
                  label="事件游标"
                  value={String(lastSequence)}
                  mono
                />
                <InspectorRow
                  label="最近同步"
                  value={formatDateTime(readModel.updated_at)}
                  mono
                />
              </InspectorSection>

              {readModel.pending_decisions.length ? (
                <InspectorSection
                  icon={<AlertTriangle size={13} />}
                  tone="warning"
                  title="待处理决策"
                >
                  {readModel.pending_decisions.map((decision) => (
                    <div
                      className="phase32-monitor-decision"
                      key={decision.decision_id}
                    >
                      <strong>{stageLabel(run, decision.stage_id)}</strong>
                      <span>{decision.unit_ref || "聚合阶段"}</span>
                      <code>{shortRef(decision.artifact_ref)}</code>
                    </div>
                  ))}
                </InspectorSection>
              ) : null}

              <InspectorSection
                icon={<FileCheck2 size={13} />}
                title="运行证据"
              >
                <SignalRow label="审阅" value={categoryCounts.review ?? 0} />
                <SignalRow
                  label="Evidence"
                  value={categoryCounts.evidence ?? 0}
                />
                <SignalRow
                  label="Writeback"
                  value={categoryCounts.writeback ?? 0}
                />
                <SignalRow
                  label="Checkpoint"
                  value={categoryCounts.checkpoint ?? 0}
                />
                <SignalRow
                  label="异常"
                  value={categoryCounts.failure ?? 0}
                  tone="risk"
                />
              </InspectorSection>

              <InspectorSection icon={<Cpu size={13} />} title="Provider 用量">
                <InspectorRow
                  label="成功 / 调用"
                  value={`${usage.succeeded_operations}/${usage.provider_operations}`}
                  mono
                />
                <InspectorRow
                  label="Token"
                  value={formatNumber(usage.total_tokens)}
                  mono
                />
                <InspectorRow
                  label="合同拒绝"
                  value={String(usage.contract_rejected_operations)}
                  mono
                />
                <InspectorRow
                  label="失败 / 等待"
                  value={`${usage.failed_operations} / ${usage.pending_operations}`}
                  mono
                />
              </InspectorSection>

              <InspectorSection
                icon={<CircleDollarSign size={13} />}
                title="成本状态"
              >
                <InspectorRow
                  label="计价"
                  value={costStatusLabel(usage.cost_status)}
                />
                <InspectorRow
                  label="预估成本"
                  value={
                    usage.estimated_cost_usd === null
                      ? "未提供"
                      : `$${usage.estimated_cost_usd.toFixed(6)}`
                  }
                  mono
                />
                <InspectorRow
                  label="余额"
                  value={balanceStatusLabel(usage.balance_status)}
                />
              </InspectorSection>

              <InspectorSection
                icon={<DatabaseZap size={13} />}
                title="恢复边界"
              >
                <InspectorRow
                  label="Checkpoint"
                  value={readModel.checkpoint_id || "尚未写入"}
                  mono
                  wrap
                />
                <InspectorRow
                  label="Definition"
                  value={readModel.definition_digest.slice(0, 12)}
                  mono
                />
                <InspectorRow
                  label="Route"
                  value={`${summary.route_revision} · ${summary.route_label}`}
                />
              </InspectorSection>

              {usage.by_provider.length ? (
                <InspectorSection icon={<Cpu size={13} />} title="服务商">
                  {usage.by_provider.map((provider) => (
                    <div
                      className="phase32-monitor-provider"
                      key={`${provider.provider_profile_id}:${provider.model_id}`}
                    >
                      <strong>{provider.model_id}</strong>
                      <span>
                        {provider.provider_template_id} · {provider.operations}{" "}
                        次
                      </span>
                    </div>
                  ))}
                </InspectorSection>
              ) : null}
            </>
          ) : (
            <section className="phase32-monitor-log" role="tabpanel">
              <header>
                <div>
                  <ScrollText size={13} />
                  <span>正式 Run 事件</span>
                </div>
                <strong>
                  最近 {visibleEvents.length}/{events.length} 条
                </strong>
              </header>
              {visibleEvents.length ? (
                <ol>
                  {visibleEvents.map((event) => (
                    <LogEvent event={event} key={event.event_id} />
                  ))}
                </ol>
              ) : (
                <p className="phase32-monitor-log-empty">尚无正式运行事件。</p>
              )}
            </section>
          )}
        </div>
      </aside>
    </Fragment>
  )
}

function LogEvent({ event }: { event: Phase32RunEvent }) {
  const category = eventCategory(event)
  const detail = phase32RunEventDetail(event)
  return (
    <li className={`is-${category}`}>
      <div>
        <span>{phase32RunEventLabel(event.type)}</span>
        <time>{formatPhase32RunEventClock(event.occurred_at)}</time>
      </div>
      <p>
        {event.stage_id || "run"}
        {event.unit_ref ? ` · ${event.unit_ref}` : ""}
      </p>
      <code title={detail}>{detail}</code>
      <small>#{event.sequence}</small>
    </li>
  )
}

function InspectorSection({
  children,
  icon,
  title,
  tone = "default",
}: {
  children: ReactNode
  icon: ReactNode
  title: string
  tone?: "default" | "risk" | "warning"
}) {
  return (
    <section className={`phase32-monitor-inspector-section is-${tone}`}>
      <h2>
        <span>{icon}</span>
        {title}
      </h2>
      <div>{children}</div>
    </section>
  )
}

function InspectorRow({
  label,
  mono = false,
  value,
  wrap = false,
}: {
  label: string
  mono?: boolean
  value: string
  wrap?: boolean
}) {
  return (
    <div className="phase32-monitor-inspector-row">
      <span>{label}</span>
      <strong className={`${mono ? "font-mono" : ""} ${wrap ? "is-wrap" : ""}`}>
        {value || "-"}
      </strong>
    </div>
  )
}

function SignalRow({
  label,
  tone = "default",
  value,
}: {
  label: string
  tone?: "default" | "risk"
  value: number
}) {
  return (
    <div className={`phase32-monitor-signal is-${tone}`}>
      {tone === "risk" ? (
        <AlertTriangle size={11} />
      ) : (
        <CheckCircle2 size={11} />
      )}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function stageLabel(run: Phase32RunEnvelope, stageId: string) {
  return (
    run.read_model.stage_manifest.find((stage) => stage.stage_id === stageId)
      ?.label ?? stageId
  )
}

function connectionLabel(value: RunConnectionState) {
  if (value === "live") return "实时"
  if (value === "connecting") return "连接中"
  if (value === "reconnecting") return "恢复连接"
  if (value === "closed") return "静默终点"
  if (value === "error") return "连接异常"
  return "未连接"
}

function runStatusLabel(value: string) {
  if (value === "created") return "待启动"
  if (value === "running") return "运行中"
  if (value === "awaiting_decision") return "等待作者决策"
  if (value === "image_deferred") return "图片验收暂缓"
  if (value === "completed") return "已完成"
  if (value === "failed") return "运行失败"
  if (value === "cancelled") return "已取消"
  return value
}

function costStatusLabel(value: string) {
  if (value === "known") return "可核算"
  if (value === "unknown") return "价格未知"
  return "不可用"
}

function balanceStatusLabel(value: string) {
  if (value === "available") return "可用"
  if (value === "insufficient") return "不足"
  if (value === "unavailable") return "不可查询"
  return "未知"
}

function formatDateTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
}

function formatNumber(value: number) {
  return value.toLocaleString("zh-CN")
}

function shortRef(value: string) {
  return value.length > 30 ? `${value.slice(0, 15)}…${value.slice(-8)}` : value
}
