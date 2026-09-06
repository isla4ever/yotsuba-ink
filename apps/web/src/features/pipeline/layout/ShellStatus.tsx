import { AlertTriangle, CheckCircle, Lock, Wifi, WifiOff } from "lucide-react"
import type { StageStatus } from "../contracts/app"
import { useApp } from "../state/PipelineAppProvider"

export function StatusDot({ status }: { status: StageStatus }) {
  if (status === "committed")
    return (
      <span className="w-1.5 h-1.5 rounded-full bg-mint inline-block shrink-0" />
    )
  if (status === "active")
    return (
      <span className="w-1.5 h-1.5 rounded-full bg-action inline-block status-quiet shrink-0" />
    )
  if (status === "warning")
    return (
      <span className="w-1.5 h-1.5 rounded-full bg-amber inline-block shrink-0" />
    )
  if (status === "blocked" || status === "failed")
    return (
      <span className="w-1.5 h-1.5 rounded-full bg-risk inline-block shrink-0" />
    )
  return null
}

export function RunConnectionStatus() {
  const { activeProject, activeRun, runConnection, runError, runLoading } =
    useApp()
  if (runLoading)
    return (
      <span className="flex items-center gap-1.5 text-xs text-fog">
        同步 Run…
      </span>
    )
  if (!activeProject?.latestRunId)
    return (
      <span className="flex items-center gap-1.5 text-xs text-fog">
        尚未启动
      </span>
    )
  if (activeProject.architectureVersion === "phase32-routes-v1" && !activeRun) {
    if (activeProject.runStatus === "running")
      return (
        <span className="flex items-center gap-1.5 text-xs text-action">
          <span className="w-1.5 h-1.5 rounded-full bg-action status-quiet" />{" "}
          运行中
        </span>
      )
    if (activeProject.runStatus === "awaiting_decision")
      return (
        <span className="flex items-center gap-1.5 text-xs text-amber">
          <AlertTriangle size={11} /> 等待决策
        </span>
      )
    if (activeProject.runStatus === "image_deferred")
      return (
        <span className="flex items-center gap-1.5 text-xs text-amber">
          <AlertTriangle size={11} /> 图片验收暂缓
        </span>
      )
    if (activeProject.runStatus === "completed")
      return (
        <span className="flex items-center gap-1.5 text-xs text-mint">
          <CheckCircle size={11} /> 已完成
        </span>
      )
    if (["failed", "cancelled"].includes(activeProject.runStatus))
      return (
        <span className="flex items-center gap-1.5 text-xs text-risk">
          <AlertTriangle size={11} /> 已停止
        </span>
      )
    return (
      <span className="flex items-center gap-1.5 text-xs text-fog">
        <Wifi size={11} /> 待启动
      </span>
    )
  }
  if (runError && !activeRun)
    return (
      <span className="flex items-center gap-1.5 text-xs text-risk">
        <AlertTriangle size={11} /> 状态异常
      </span>
    )
  if (activeRun?.read_model.status === "running")
    return (
      <span className="flex items-center gap-1.5 text-xs text-action">
        <span className="w-1.5 h-1.5 rounded-full bg-action status-quiet" />{" "}
        运行中
      </span>
    )
  if (activeRun?.read_model.status === "awaiting_decision")
    return (
      <span className="flex items-center gap-1.5 text-xs text-amber">
        <AlertTriangle size={11} /> 等待决策
      </span>
    )
  if (activeRun?.read_model.status === "image_deferred")
    return (
      <span className="flex items-center gap-1.5 text-xs text-amber">
        <AlertTriangle size={11} /> 图片验收暂缓
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

export function RouteLockBadge({ label }: { label: string }) {
  return (
    <div className="route-lock-badge" title="本书创作路线已在立项时冻结。">
      <span className="mode-swatch bg-action" />
      <Lock size={9} className="opacity-50" />
      <span>{label}</span>
    </div>
  )
}
