import {
  AlertTriangle,
  CheckCircle,
  Lock,
  Wifi,
  WifiOff,
} from "lucide-react"
import type { StageStatus } from "../contracts/app"
import { useApp } from "../state/PipelineAppProvider"

const MODE_META: Record<string, { label: string; color: string }> = {
  fast: { label: "极速", color: "#4f7fd4" },
  balanced: { label: "均衡", color: "#3db89a" },
  deep: { label: "精细", color: "#8b65c0" },
}

const LOCK_TOOLTIP =
  "本书模式已在立项时锁定；如需更换，请从创作台复制为新配置后重新开始。"

export function StatusDot({ status }: { status: StageStatus }) {
  if (status === "committed")
    return <span className="w-1.5 h-1.5 rounded-full bg-mint inline-block shrink-0" />
  if (status === "active")
    return <span className="w-1.5 h-1.5 rounded-full bg-action inline-block status-quiet shrink-0" />
  if (status === "warning")
    return <span className="w-1.5 h-1.5 rounded-full bg-amber inline-block shrink-0" />
  if (status === "blocked" || status === "failed")
    return <span className="w-1.5 h-1.5 rounded-full bg-risk inline-block shrink-0" />
  return null
}

export function RunConnectionStatus() {
  const { activeProject, activeRun, runConnection, runError, runLoading } =
    useApp()
  if (runLoading)
    return <span className="flex items-center gap-1.5 text-xs text-fog">同步 Run…</span>
  if (!activeProject?.latestRunId)
    return <span className="flex items-center gap-1.5 text-xs text-fog">尚未启动</span>
  if (runError && !activeRun)
    return (
      <span className="flex items-center gap-1.5 text-xs text-risk">
        <AlertTriangle size={11} /> 状态异常
      </span>
    )
  if (activeRun?.read_model.status === "running")
    return (
      <span className="flex items-center gap-1.5 text-xs text-action">
        <span className="w-1.5 h-1.5 rounded-full bg-action status-quiet" /> 运行中
      </span>
    )
  if (activeRun?.read_model.status === "awaiting_decision")
    return (
      <span className="flex items-center gap-1.5 text-xs text-amber">
        <AlertTriangle size={11} /> 等待决策
      </span>
    )
  if (activeRun?.read_model.status === "completed")
    return (
      <span className="flex items-center gap-1.5 text-xs text-mint">
        <CheckCircle size={11} /> 已完成
      </span>
    )
  if (["failed", "cancelled"].includes(activeRun?.read_model.status ?? ""))
    return (
      <span className="flex items-center gap-1.5 text-xs text-risk">
        <AlertTriangle size={11} /> 已停止
      </span>
    )
  if (runConnection === "reconnecting")
    return (
      <span className="flex items-center gap-1.5 text-xs text-amber">
        <WifiOff size={11} /> 重连中
      </span>
    )
  return (
    <span className="flex items-center gap-1.5 text-xs text-fog">
      <Wifi size={11} /> 待启动
    </span>
  )
}

export function ModeLockBadge({ mode, model }: { mode: string; model?: string }) {
  const meta = MODE_META[mode] ?? MODE_META.balanced
  return (
    <div className="mode-lock-badge" title={LOCK_TOOLTIP}>
      <span className="mode-swatch" style={{ background: meta.color }} />
      <Lock size={9} className="opacity-50" />
      <span>{meta.label}</span>
      {model && (
        <span className="font-mono text-[10.5px] opacity-40 hidden lg:inline">
          {model}
        </span>
      )}
    </div>
  )
}
