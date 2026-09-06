import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleDashed,
  LockKeyhole,
  Radio,
  XCircle,
} from "lucide-react"
import { useEffect, useRef } from "react"
import type {
  Phase32RouteStageManifest,
  Phase32RunReadModel,
  Phase32StageStatus,
} from "../../contracts/run"
import { monitorUnitRefs, monitorUnitState } from "../../lib/phase32RunMonitor"

type Props = {
  activeStageId: string
  manifest: Phase32RouteStageManifest[]
  onSelect: (stageId: string) => void
  onSelectUnit: (unitRef: string) => void
  readModel: Phase32RunReadModel
  selectedStageId: string
  selectedUnitRef: string
  statuses: Record<string, Phase32StageStatus>
}

const STATUS_LABELS: Record<Phase32StageStatus, string> = {
  locked: "锁定",
  available: "可开始",
  running: "运行中",
  awaiting_decision: "待决策",
  stale: "需重建",
  completed: "已提交",
  failed: "异常",
}

export function Phase32RunMonitorRail({
  activeStageId,
  manifest,
  onSelect,
  onSelectUnit,
  readModel,
  selectedStageId,
  selectedUnitRef,
  statuses,
}: Props) {
  const selectedStageRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (typeof selectedStageRef.current?.scrollIntoView !== "function") return
    selectedStageRef.current.scrollIntoView({
      block: "nearest",
      inline: "nearest",
    })
  }, [selectedStageId])

  return (
    <aside className="phase32-monitor-rail">
      <div className="phase32-monitor-rail-heading">
        <p className="text-[10px] uppercase text-fog">RUN STAGES</p>
        <h2>阶段与创作单元</h2>
      </div>
      <nav aria-label="监控阶段" className="phase32-monitor-rail-list">
        {manifest.map((stage) => {
          const status = statuses[stage.stage_id] ?? "locked"
          const selected = selectedStageId === stage.stage_id
          const active = activeStageId === stage.stage_id
          const StatusIcon = statusIcon(status)
          const unitRefs = selected
            ? monitorUnitRefs(readModel, stage.stage_id)
            : []
          return (
            <div className="phase32-monitor-rail-group" key={stage.stage_id}>
              <button
                type="button"
                aria-current={selected ? "true" : undefined}
                className={`phase32-monitor-stage ${
                  selected ? "is-selected" : ""
                }`}
                onClick={() => onSelect(stage.stage_id)}
                ref={selected ? selectedStageRef : undefined}
              >
                <span
                  className={`phase32-monitor-stage-index ${
                    selected
                      ? "border-action/35 bg-action-bg text-action"
                      : "border-hairline bg-base text-fog"
                  }`}
                >
                  {String(stage.ordinal + 1).padStart(2, "0")}
                </span>
                <span className="phase32-monitor-stage-copy">
                  <span>{stage.label}</span>
                  <small>
                    <StatusIcon size={10} aria-hidden="true" />
                    {STATUS_LABELS[status]}
                    {active && <i>当前</i>}
                  </small>
                </span>
                {unitRefs.length ? <ChevronDown size={12} /> : null}
              </button>
              {unitRefs.length ? (
                <div
                  className="phase32-monitor-units"
                  aria-label={`${stage.label}单元`}
                >
                  {unitRefs.map((unitRef, index) => {
                    const unitState = monitorUnitState(
                      readModel,
                      stage.stage_id,
                      unitRef,
                    )
                    const UnitIcon = unitStateIcon(unitState)
                    return (
                      <button
                        aria-current={
                          selectedUnitRef === unitRef ? "step" : undefined
                        }
                        className={
                          selectedUnitRef === unitRef ? "is-selected" : ""
                        }
                        key={unitRef}
                        onClick={() => onSelectUnit(unitRef)}
                        type="button"
                      >
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <span title={unitRef}>{unitLabel(unitRef)}</span>
                        <UnitIcon size={10} className={`is-${unitState}`} />
                      </button>
                    )
                  })}
                </div>
              ) : null}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}

function statusIcon(status: Phase32StageStatus) {
  if (status === "completed") return Check
  if (status === "awaiting_decision") return AlertTriangle
  if (status === "stale") return AlertTriangle
  if (status === "failed") return XCircle
  if (status === "locked") return LockKeyhole
  return CircleDashed
}

function unitStateIcon(state: ReturnType<typeof monitorUnitState>) {
  if (state === "committed") return Check
  if (state === "failed") return XCircle
  if (state === "active") return Radio
  return CircleDashed
}

function unitLabel(value: string) {
  const match = value.match(
    /^(scene|chapter|unit|section|part|volume|window)[-_](\d+)$/i,
  )
  if (!match) return value
  const labels: Record<string, string> = {
    chapter: "章节",
    part: "Part",
    scene: "场景",
    section: "段落",
    unit: "单元",
    volume: "卷",
    window: "窗口",
  }
  return `${labels[match[1].toLowerCase()] ?? match[1]} ${match[2]}`
}
