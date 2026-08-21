import { useEffect, useMemo, useState } from "react"
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle,
  Clock,
  FolderOpen,
  RefreshCw,
  Scale,
  XCircle,
  Zap,
} from "lucide-react"
import { useApp } from "../../state/PipelineAppProvider"
import type {
  RunHistoryItem,
  RunHistoryStatus,
} from "@/features/pipeline/contracts/runHistory"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { projectPresentation } from "@/features/pipeline/lib/projectPresentation"
import { getProjectSummary } from "@/features/pipeline/services/projectApi"
import { listRunHistory } from "@/features/pipeline/services/runHistoryApi"

const MODE_ICONS = {
  fast: <Zap size={12} className="text-fast" />,
  balanced: <Scale size={12} className="text-balanced" />,
  deep: <Brain size={12} className="text-deep" />,
}

const STATUS_CONFIG: Record<RunHistoryStatus, {
  icon: typeof Clock
  label: string
  color: string
}> = {
  created: { icon: Clock, label: "已创建", color: "text-fog" },
  running: { icon: Activity, label: "运行中", color: "text-action" },
  awaiting_decision: {
    icon: AlertTriangle,
    label: "等待决策",
    color: "text-amber",
  },
  failed: { icon: XCircle, label: "失败", color: "text-risk" },
  completed: { icon: CheckCircle, label: "已完成", color: "text-mint" },
  cancelled: { icon: XCircle, label: "已取消", color: "text-fog" },
}

export default function HistoryPage() {
  const { openProject } = useApp()
  const [items, setItems] = useState<RunHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [openingId, setOpeningId] = useState("")
  const totals = useMemo(
    () => ({
      tokens: items.reduce((sum, item) => sum + item.total_tokens, 0),
      words: items.reduce((sum, item) => sum + item.words, 0),
      completed: items.filter((item) => item.status === "completed").length,
    }),
    [items],
  )

  const load = () => {
    const controller = new AbortController()
    setLoading(true)
    setError("")
    void listRunHistory({ limit: 50 }, controller.signal)
      .then((payload) => setItems(payload.items))
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error ? reason.message : "创作历史读取失败",
          )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }

  useEffect(load, [])
  const initialLoad = useLoadingPresence(loading && items.length === 0)

  const openHistoryProject = async (item: RunHistoryItem) => {
    setOpeningId(item.run_id)
    setError("")
    try {
      const summary = await getProjectSummary(item.project_id)
      openProject(projectPresentation(summary.project, summary))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法打开该作品")
    } finally {
      setOpeningId("")
    }
  }

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在整理创作历史"
        detail="同步 Run、阶段状态、Token 与导出回执"
      />
    )
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <div className="border-b border-hairline bg-surface px-6 py-3 flex items-center gap-3 shrink-0">
        <Clock size={14} className="text-fog" />
        <span className="text-sm font-medium text-ink">创作历史</span>
        <span className="text-xs text-fog">· 服务器 Run 只读记录</span>
        <div className="flex-1" />
        <span className="hidden md:inline text-xs font-mono text-fog">
          {items.length} 条 · {totals.tokens.toLocaleString("zh-CN")} Token
        </span>
        <button
          type="button"
          className="btn btn-ghost p-1.5"
          onClick={load}
          aria-label="刷新创作历史"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-4 md:px-6 py-5">
          {error && (
            <div className="banner-warning mb-4" role="alert">
              {error}
            </div>
          )}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <HistoryStat
              label="运行记录"
              value={String(items.length)}
              sub={`${totals.completed} 个已完成`}
            />
            <HistoryStat
              label="累计正文"
              value={formatCompact(totals.words)}
              sub="已接受章节字符投影"
            />
            <HistoryStat
              label="累计用量"
              value={formatCompact(totals.tokens)}
              sub="Provider Token"
            />
          </div>

          {items.length === 0 ? (
            <div className="bg-surface border border-dashed border-hairline rounded-lg py-16 text-center">
              <Clock size={22} className="text-fog mx-auto mb-3 opacity-50" />
              <strong className="block text-sm text-ink mb-1">
                暂无创作 Run
              </strong>
              <span className="text-xs text-fog">
                新作品启动创作后，真实阶段历史会出现在这里。
              </span>
            </div>
          ) : (
            <div className="bg-surface border border-hairline rounded-lg overflow-hidden">
              <div className="hidden md:grid grid-cols-12 px-4 py-2 bg-hover text-[10px] text-fog uppercase tracking-wider">
                <span className="col-span-3">作品 / Run</span>
                <span className="col-span-2">更新时间</span>
                <span className="col-span-2">阶段</span>
                <span className="col-span-2">产出</span>
                <span className="col-span-1">模式</span>
                <span className="col-span-1">状态</span>
                <span className="col-span-1" />
              </div>
              {items.map((item) => (
                <HistoryRow
                  key={item.run_id}
                  item={item}
                  opening={openingId === item.run_id}
                  onOpen={() => void openHistoryProject(item)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function HistoryStat({
  label,
  sub,
  value,
}: {
  label: string
  sub: string
  value: string
}) {
  return (
    <div className="bg-surface border border-hairline rounded-lg px-4 py-3 min-w-0">
      <div className="text-xs text-fog mb-1">{label}</div>
      <div className="text-xl font-bold text-ink font-mono truncate">
        {value}
      </div>
      <div className="text-[10px] text-fog truncate">{sub}</div>
    </div>
  )
}

function HistoryRow({
  item,
  onOpen,
  opening,
}: {
  item: RunHistoryItem
  onOpen: () => void
  opening: boolean
}) {
  const status = STATUS_CONFIG[item.status]
  const StatusIcon = status.icon
  return (
    <article className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-0 items-center px-4 py-3 border-t border-ghost hover:bg-hover transition-colors">
      <div className="md:col-span-3 min-w-0">
        <strong className="block text-xs text-ink truncate">
          《{item.title}》
        </strong>
        <span className="block font-mono text-[10px] text-fog truncate">
          {item.run_id}
        </span>
      </div>
      <span className="md:col-span-2 font-mono text-[10px] text-fog">
        {formatDate(item.updated_at)}
      </span>
      <div className="md:col-span-2 min-w-0">
        <span className="text-xs text-ash">
          {item.current_stage.label || "尚未开始"}
        </span>
        <span className="block text-[10px] text-fog truncate">
          {item.summary}
        </span>
      </div>
      <div className="md:col-span-2 text-[10px] text-fog font-mono">
        {item.words.toLocaleString("zh-CN")} 字 ·{" "}
        {formatCompact(item.total_tokens)} T
      </div>
      <span className="md:col-span-1">{MODE_ICONS[item.quality_mode]}</span>
      <span
        className={`md:col-span-1 flex items-center gap-1 ${status.color}`}
        title={status.label}
      >
        <StatusIcon size={13} />
        <span className="md:hidden text-xs">{status.label}</span>
      </span>
      <button
        type="button"
        className="md:col-span-1 btn btn-ghost p-1.5 justify-self-start md:justify-self-end"
        onClick={onOpen}
        disabled={opening}
        aria-label={`打开${item.title}`}
      >
        {opening ? (
          <RefreshCw size={13} className="animate-spin" />
        ) : (
          <FolderOpen size={13} />
        )}
      </button>
    </article>
  )
}

function formatCompact(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
}
