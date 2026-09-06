import { CheckCircle2, CircleDashed, LockKeyhole } from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"

export default function Phase32StageStatusView() {
  const { activeProject, activeRun, route, runError, runLoading } = useApp()
  if (!activeProject) return null

  const runStage = activeRun?.read_model.stage_manifest.find(
    (item) => item.stage_id === route,
  )
  const projectStage = activeProject.stageManifest.find(
    (item) => item.id === route,
  )
  const stage = runStage
    ? {
        id: runStage.stage_id,
        label: runStage.label,
        ordinal: runStage.ordinal,
      }
    : projectStage
  const runStatus = stage
    ? activeRun?.read_model.stage_status[stage.id]
    : undefined
  const status =
    runStatus ?? (stage ? activeProject.stageStatuses[stage.id] : "pending")
  const Icon =
    status === "completed" || status === "committed"
      ? CheckCircle2
      : status === "pending" || status === "locked"
        ? LockKeyhole
        : CircleDashed

  return (
    <div className="grid min-h-0 flex-1 place-items-center overflow-y-auto bg-base px-5 py-8 page-in">
      <section className="w-full max-w-2xl border-y border-hairline bg-surface/45 px-6 py-8 text-center">
        <Icon size={22} className="mx-auto mb-3 text-action" />
        <p className="mb-1 text-[10px] uppercase text-fog">
          {activeProject.routeLabel} · {stage ? stage.ordinal + 1 : "-"}
        </p>
        <h1 className="text-base font-semibold text-ink">
          {stage?.label ?? "阶段不可用"}
        </h1>
        <p className="mt-3 text-xs text-fog">
          {runLoading
            ? "正在同步该阶段的权威 Run 状态。"
            : runError
              ? runError
              : status === "pending" || status === "locked"
                ? "上游 Artifact 尚未提交，本阶段保持锁定。"
                : `当前阶段状态：${status}`}
        </p>
      </section>
    </div>
  )
}
