import {
  Activity,
  BarChart3,
  BookOpen,
  Clapperboard,
  Download,
  FileText,
  GitBranch,
  Image,
  Layers,
  ListOrdered,
  Network,
  Pencil,
  ScrollText,
  Users,
} from "lucide-react"
import type { ReactNode } from "react"
import { useId } from "react"
import type { Project, Route } from "../contracts/app"
import type { Phase32RunEnvelope } from "../contracts/run"
import { runStageStatuses } from "../lib/runPresentation"
import { useApp } from "../state/PipelineAppProvider"

export type StageNavigationItem = {
  id: Route
  label: string
  num: number
  icon: ReactNode
}

export function projectStageNavigation(
  project: Project,
): StageNavigationItem[] {
  return project.stageManifest.map((stage) => ({
    id: stage.id as Route,
    label: stage.label,
    num: stage.ordinal + 1,
    icon: stageIcon(stage.id),
  }))
}

export function runStageNavigation(
  run: Phase32RunEnvelope,
): StageNavigationItem[] {
  return run.read_model.stage_manifest.map((stage) => ({
    id: stage.stage_id as Route,
    label: stage.label,
    num: stage.ordinal + 1,
    icon: stageIcon(stage.stage_id),
  }))
}

export function StageProgressTrace({
  route,
  setRoute,
}: {
  route: Route
  setRoute: (route: Route) => void
}) {
  const { activeProject, activeRun } = useApp()
  const stages = activeRun
    ? runStageNavigation(activeRun)
    : activeProject
      ? projectStageNavigation(activeProject)
      : []
  const statuses = runStageStatuses(
    activeRun,
    activeProject?.stageStatuses ?? {},
  )
  const runStatus = activeRun?.read_model.status ?? activeProject?.runStatus
  const stageCount = stages.length
  const committedCount = stages.filter(
    (stage) => statuses[stage.id] === "committed",
  ).length
  const activeIndex = stages.findIndex((stage) =>
    ["active", "warning", "blocked", "failed"].includes(statuses[stage.id]),
  )
  const cursorPct =
    stageCount === 0
      ? 0
      : activeIndex >= 0
        ? ((activeIndex + 0.5) / stageCount) * 100
        : committedCount === stageCount
          ? 100
          : (committedCount / stageCount) * 100
  const tracePath = stageTracePath(stages, statuses, activeIndex)
  const activePulsePath =
    activeIndex >= 0 && runStatus === "running"
      ? stagePulsePath(stages, activeIndex)
      : ""
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
        {stages.map((stage, index) => {
          const disabled = statuses[stage.id] === "pending"
          return (
            <button
              key={stage.id}
              onClick={() => setRoute(stage.id)}
              disabled={disabled}
              className="stage-progress-hit"
              style={{
                width: `${(1 / stageCount) * 100}%`,
                left: `${(index / stageCount) * 100}%`,
              }}
              title={`${stage.num}·${stage.label}`}
              aria-label={`${stage.num}·${stage.label}`}
            />
          )
        })}
      </div>
      <div
        className="stage-progress-labels"
        style={{
          gridTemplateColumns: `repeat(${Math.max(stageCount, 1)}, minmax(0, 1fr))`,
        }}
      >
        {stages.map((stage) => {
          const status = statuses[stage.id]
          const isCurrent = route === stage.id
          const isActive = status === "active"
          const isCommitted = status === "committed"
          const stateLabel = stageStateLabel(status, runStatus)
          return (
            <button
              key={stage.id}
              onClick={() => setRoute(stage.id)}
              disabled={status === "pending"}
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
  stages: StageNavigationItem[],
  statuses: Record<string, string>,
  activeIndex: number,
) {
  const baseline = 17
  const width = 560
  const segment = width / Math.max(stages.length, 1)
  const points = [`M0 ${baseline}`]
  stages.forEach((stage, index) => {
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

function stagePulsePath(stages: StageNavigationItem[], activeIndex: number) {
  const baseline = 17
  const segment = 560 / Math.max(stages.length, 1)
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

function stageIcon(stageId: string) {
  if (stageId === "brief") return <Pencil size={14} />
  if (stageId === "cast") return <Users size={14} />
  if (stageId === "beat_board") return <Activity size={14} />
  if (stageId === "scene_deck") return <Clapperboard size={14} />
  if (stageId === "script") return <ScrollText size={14} />
  if (stageId === "story_map") return <GitBranch size={14} />
  if (stageId === "section_plan") return <ListOrdered size={14} />
  if (stageId === "book_architecture") return <Network size={14} />
  if (stageId === "volumes") return <BarChart3 size={14} />
  if (stageId === "rolling_detail") return <BookOpen size={14} />
  if (stageId === "text") return <FileText size={14} />
  if (stageId === "cover") return <Image size={14} />
  if (stageId === "export") return <Download size={14} />
  return <Layers size={14} />
}

function stageStateLabel(status: string | undefined, runStatus?: string) {
  if (status === "active") return runStatus === "created" ? "待启动" : "运行中"
  if (status === "warning") return "待确认"
  if (status === "failed") return "异常"
  if (status === "blocked") return "阻塞"
  return ""
}
