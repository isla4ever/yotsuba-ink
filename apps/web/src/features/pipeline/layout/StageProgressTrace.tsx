import {
  BarChart3,
  BookOpen,
  Download,
  FileText,
  Image,
  Layers,
  Pencil,
  Users,
} from "lucide-react"
import type { ReactNode } from "react"
import { useId } from "react"
import type { Route } from "../contracts/app"
import { runStageStatuses } from "../lib/runPresentation"
import { useApp } from "../state/PipelineAppProvider"

export const STAGES: Array<{
  id: Route
  label: string
  num: number
  icon: ReactNode
}> = [
  { id: "brief", label: "简报", num: 1, icon: <Pencil size={14} /> },
  { id: "spine", label: "脊柱", num: 2, icon: <Layers size={14} /> },
  { id: "cast", label: "角色", num: 3, icon: <Users size={14} /> },
  { id: "volumes", label: "卷册", num: 4, icon: <BarChart3 size={14} /> },
  { id: "detail", label: "细纲", num: 5, icon: <BookOpen size={14} /> },
  { id: "text", label: "正文", num: 6, icon: <FileText size={14} /> },
  { id: "cover", label: "封面", num: 7, icon: <Image size={14} /> },
  { id: "export", label: "导出", num: 8, icon: <Download size={14} /> },
]

export function StageProgressTrace({
  route,
  setRoute,
}: {
  route: Route
  setRoute: (route: Route) => void
}) {
  const { activeProject, activeRun } = useApp()
  const statuses = runStageStatuses(
    activeRun,
    activeProject?.stageStatuses ?? {},
  )
  const stageCount = STAGES.length
  const committedCount = STAGES.filter(
    (stage) => statuses[stage.id] === "committed",
  ).length
  const activeIndex = STAGES.findIndex((stage) =>
    ["active", "warning", "blocked", "failed"].includes(statuses[stage.id]),
  )
  const cursorPct = activeIndex >= 0
    ? ((activeIndex + 0.5) / stageCount) * 100
    : committedCount === stageCount
      ? 100
      : (committedCount / stageCount) * 100
  const tracePath = stageTracePath(statuses, activeIndex)
  const activePulsePath = activeIndex >= 0 ? stagePulsePath(activeIndex) : ""
  const clipId = useId().replace(/:/g, "")

  return (
    <nav className="stage-progress-trace" aria-label="创作阶段进度">
      <div className="stage-progress-wave">
        <svg aria-hidden="true" preserveAspectRatio="none" viewBox="0 0 560 28">
          <defs>
            <clipPath id={clipId}>
              <rect height="28" width={`${cursorPct}%`} x="0" y="0" />
            </clipPath>
          </defs>
          <path className="stage-progress-baseline" d="M0 17 H560" />
          <path className="stage-progress-shape" d={tracePath} />
          <path
            className="stage-progress-complete"
            clipPath={`url(#${clipId})`}
            d={tracePath}
          />
          {activePulsePath && (
            <path
              className="stage-progress-live-beat"
              d={activePulsePath}
              key={`${activeRun?.read_model.active_stage_id ?? "idle"}-${activeRun?.read_model.updated_at ?? ""}`}
            />
          )}
        </svg>
        <span
          aria-hidden="true"
          className="stage-progress-cursor ecg-cursor-enter"
          style={{ left: `${cursorPct}%` }}
        />
        {STAGES.map((stage, index) => (
          <button
            key={stage.id}
            onClick={() => setRoute(stage.id)}
            className="stage-progress-hit"
            style={{
              width: `${(1 / stageCount) * 100}%`,
              left: `${(index / stageCount) * 100}%`,
            }}
            title={`${stage.num}·${stage.label}`}
            aria-label={`${stage.num}·${stage.label}`}
          />
        ))}
      </div>
      <div className="stage-progress-labels">
        {STAGES.map((stage) => {
          const status = statuses[stage.id]
          const isCurrent = route === stage.id
          const isActive = status === "active"
          const isCommitted = status === "committed"
          const stateLabel = stageStateLabel(status)
          return (
            <button
              key={stage.id}
              onClick={() => setRoute(stage.id)}
              aria-current={isCurrent ? "step" : undefined}
              className={`${isCurrent ? "current" : ""} ${
                isActive ? "active" : ""
              } ${isCommitted ? "committed" : ""}`}
            >
              <span>{stage.label}</span>
              {stateLabel && <small>{stateLabel}</small>}
            </button>
          )
        })}
      </div>
    </nav>
  )
}

function stageTracePath(
  statuses: Record<string, string>,
  activeIndex: number,
) {
  const baseline = 17
  const width = 560
  const segment = width / STAGES.length
  const points = [`M0 ${baseline}`]
  STAGES.forEach((stage, index) => {
    const x = segment * (index + 0.5)
    const committed = statuses[stage.id] === "committed"
    const amplitude = index === activeIndex ? 12 : committed ? 5 : 2
    points.push(
      `L${(x - 13).toFixed(1)} ${baseline}`,
      `L${(x - 6).toFixed(1)} ${baseline}`,
      `L${(x - 2).toFixed(1)} ${(baseline - amplitude * 0.34).toFixed(1)}`,
      `L${x.toFixed(1)} ${(baseline - amplitude).toFixed(1)}`,
      `L${(x + 3).toFixed(1)} ${(baseline + amplitude * 0.45).toFixed(1)}`,
      `L${(x + 7).toFixed(1)} ${baseline}`,
      `L${(x + 13).toFixed(1)} ${baseline}`,
    )
  })
  points.push(`L${width} ${baseline}`)
  return points.join(" ")
}

function stagePulsePath(activeIndex: number) {
  const baseline = 17
  const segment = 560 / STAGES.length
  const x = segment * (activeIndex + 0.5)
  return [
    `M${(x - 13).toFixed(1)} ${baseline}`,
    `L${(x - 6).toFixed(1)} ${baseline}`,
    `L${(x - 2).toFixed(1)} 12.9`,
    `L${x.toFixed(1)} 5`,
    `L${(x + 3).toFixed(1)} 22.4`,
    `L${(x + 7).toFixed(1)} ${baseline}`,
    `L${(x + 13).toFixed(1)} ${baseline}`,
  ].join(" ")
}

function stageStateLabel(status: string | undefined) {
  if (status === "active") return "运行中"
  if (status === "warning") return "待确认"
  if (status === "failed") return "异常"
  if (status === "blocked") return "阻塞"
  return ""
}
