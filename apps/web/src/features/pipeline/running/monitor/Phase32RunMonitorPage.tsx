import "../../../../styles/phase32-run-monitor.css"
import { useEffect, useMemo, useRef, useState } from "react"
import {
  AlertTriangle,
  ArrowUpRight,
  PanelRightOpen,
  Play,
  RefreshCw,
  Radio,
} from "lucide-react"
import type { Route } from "../../contracts/app"
import type { Phase32RouteStageManifest } from "../../contracts/run"
import {
  monitorUnitRefs,
  preferredMonitorUnit,
} from "../../lib/phase32RunMonitor"
import { startRun } from "../../services/runApi"
import { useApp } from "../../state/PipelineAppProvider"
import { usePhase32MonitorArtifact } from "../../state/usePhase32MonitorArtifact"
import { BookLoader } from "../../layout/BookLoader"
import { Phase32RunArtifactPreview } from "./Phase32RunArtifactPreview"
import { Phase32RunMonitorInspector } from "./Phase32RunMonitorInspector"
import { Phase32RunMonitorRail } from "./Phase32RunMonitorRail"

export default function Phase32RunMonitorPage() {
  const {
    activeProject,
    activeRun,
    reconnectRun,
    refreshRun,
    runConnection,
    runError,
    runEvents,
    runLoading,
    setRoute,
  } = useApp()
  const [selectedStageId, setSelectedStageId] = useState("")
  const [selectedUnitRef, setSelectedUnitRef] = useState("")
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [actionError, setActionError] = useState("")
  const [starting, setStarting] = useState(false)
  const initializedRunId = useRef("")
  const inspectorTriggerRef = useRef<HTMLButtonElement>(null)
  const unitPinned = useRef(false)

  const readModel = activeRun?.read_model
  const manifest = readModel?.stage_manifest ?? []
  const activeStageId = readModel?.active_stage_id ?? ""

  useEffect(() => {
    const runId = activeRun?.definition.run_id ?? ""
    if (!runId || initializedRunId.current === runId || !readModel) return
    initializedRunId.current = runId
    unitPinned.current = false
    setSelectedStageId(readModel.active_stage_id || manifest[0]?.stage_id || "")
    setSelectedUnitRef(
      preferredMonitorUnit(
        readModel,
        readModel.active_stage_id || manifest[0]?.stage_id || "",
        readModel.pending_decisions,
      ),
    )
    setInspectorOpen(false)
  }, [activeRun?.definition.run_id, manifest, readModel])

  useEffect(() => {
    if (!readModel || !manifest.length) return
    const stageId = manifest.some((stage) => stage.stage_id === selectedStageId)
      ? selectedStageId
      : readModel.active_stage_id || manifest[0].stage_id
    if (stageId !== selectedStageId) {
      unitPinned.current = false
      setSelectedStageId(stageId)
    }
    const unitRefs = monitorUnitRefs(readModel, stageId)
    if (!unitRefs.length) {
      if (selectedUnitRef) setSelectedUnitRef("")
      return
    }
    if (
      !unitPinned.current &&
      stageId === readModel.active_stage_id &&
      unitRefs.includes(readModel.active_unit_ref) &&
      selectedUnitRef !== readModel.active_unit_ref
    ) {
      setSelectedUnitRef(readModel.active_unit_ref)
      return
    }
    if (!unitRefs.includes(selectedUnitRef)) {
      setSelectedUnitRef(
        preferredMonitorUnit(readModel, stageId, readModel.pending_decisions),
      )
    }
  }, [manifest, readModel, selectedStageId, selectedUnitRef])

  const selectedStage = manifest.find(
    (stage) => stage.stage_id === selectedStageId,
  )
  const selectedStatus =
    selectedStage && readModel
      ? readModel.stage_status[selectedStage.stage_id]
      : "locked"
  const pendingDecision = readModel?.pending_decisions.find(
    (decision) =>
      decision.stage_id === selectedStageId &&
      (!selectedUnitRef || decision.unit_ref === selectedUnitRef),
  )
  const selectedEventSequence = useMemo(
    () =>
      runEvents
        .filter(
          (event) =>
            event.stage_id === selectedStageId &&
            (!selectedUnitRef ||
              !event.unit_ref ||
              event.unit_ref === selectedUnitRef),
        )
        .at(-1)?.sequence ?? 0,
    [runEvents, selectedStageId, selectedUnitRef],
  )
  const authorityRevision = [
    readModel?.artifact_refs[selectedStageId]?.artifact_ref ?? "",
    pendingDecision?.artifact_ref ?? "",
    selectedEventSequence,
  ].join(":")
  const artifactState = usePhase32MonitorArtifact({
    authorityRevision,
    runId: activeRun?.definition.run_id ?? "",
    stageId: selectedStageId,
    unitRef: selectedUnitRef,
  })

  if (runLoading && !activeRun) {
    return (
      <BookLoader
        variant="panel"
        label="正在接入运行监控"
        detail="同步动态阶段、创作内容、SSE 游标与 Provider 用量"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun || !readModel) {
    return (
      <div className="grid min-h-0 flex-1 place-items-center bg-base px-5 py-8 page-in">
        <section className="w-full max-w-xl border-y border-hairline px-5 py-7 text-center">
          <AlertTriangle size={20} className="mx-auto mb-3 text-amber" />
          <h1 className="text-sm font-semibold text-ink">无法读取正式 Run</h1>
          <p className="mt-2 text-xs leading-5 text-fog">
            {runError || "当前作品没有可监控的 Phase 32 Run。"}
          </p>
          <button
            type="button"
            className="btn btn-secondary mt-4 px-3 py-2 text-xs"
            onClick={() => void refreshRun()}
          >
            <RefreshCw size={13} />
            重新读取
          </button>
        </section>
      </div>
    )
  }

  const summary = activeRun.summary

  const handleStart = async () => {
    setStarting(true)
    setActionError("")
    try {
      await startRun(activeRun.definition.run_id)
      reconnectRun()
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Run 启动失败")
    } finally {
      setStarting(false)
    }
  }

  const selectStage = (stageId: string) => {
    unitPinned.current = false
    setSelectedStageId(stageId)
    setSelectedUnitRef(
      preferredMonitorUnit(readModel, stageId, readModel.pending_decisions),
    )
  }

  return (
    <div className="phase32-monitor-shell page-in">
      <Phase32RunMonitorRail
        activeStageId={activeStageId}
        manifest={manifest}
        onSelect={selectStage}
        onSelectUnit={(unitRef) => {
          unitPinned.current = true
          setSelectedUnitRef(unitRef)
        }}
        readModel={readModel}
        selectedStageId={selectedStageId}
        selectedUnitRef={selectedUnitRef}
        statuses={readModel.stage_status}
      />

      <main className="phase32-monitor-main">
        <header className="phase32-monitor-toolbar">
          <div className="phase32-monitor-title">
            <span>
              <Radio size={10} /> LIVE RUN CONTROL
            </span>
            <h1>
              {summary.route_label} · {summary.active_stage.label}
            </h1>
          </div>
          <div className="phase32-monitor-toolbar-actions">
            <span
              className={`phase32-monitor-run-state is-${readModel.status}`}
            >
              {runStatusLabel(readModel.status)}
            </span>
            <button
              aria-label="打开运行状态与日志"
              className="phase32-monitor-inspector-trigger"
              onClick={() => setInspectorOpen(true)}
              ref={inspectorTriggerRef}
              title="运行状态与日志"
              type="button"
            >
              <PanelRightOpen size={14} />
              <span>状态与日志</span>
            </button>
            {readModel.status === "created" ? (
              <button
                className="btn btn-primary px-3 py-2 text-xs"
                disabled={starting}
                onClick={() => void handleStart()}
                type="button"
              >
                {starting ? (
                  <RefreshCw size={13} className="animate-spin" />
                ) : (
                  <Play size={13} />
                )}
                {starting ? "启动中" : "启动流水线"}
              </button>
            ) : null}
          </div>
        </header>

        {runError || actionError ? (
          <div className="banner-warning phase32-monitor-banner" role="alert">
            {actionError || runError}
          </div>
        ) : null}

        <section className="phase32-monitor-stage-bar">
          <div>
            <span>当前查看</span>
            <strong>{selectedStage?.label ?? "阶段不可用"}</strong>
            <small>
              {selectedUnitRef || unitizationLabel(selectedStage)} ·{" "}
              {stageStatusLabel(selectedStatus)}
            </small>
          </div>
          <dl>
            <Metric
              label="阶段"
              value={`${summary.progress.completed}/${summary.progress.total}`}
            />
            <Metric
              label="Provider"
              value={`${readModel.provider_usage.succeeded_operations}/${readModel.provider_usage.provider_operations}`}
            />
            <Metric label="事件" value={String(runEvents.length)} />
          </dl>
          {selectedStage ? (
            <button
              className="btn btn-secondary"
              onClick={() => setRoute(selectedStage.stage_id as Route)}
              type="button"
            >
              前往阶段 <ArrowUpRight size={13} />
            </button>
          ) : null}
        </section>

        {pendingDecision ? (
          <div className="phase32-monitor-decision-banner" role="status">
            <AlertTriangle size={13} />
            <div>
              <strong>等待作者审阅</strong>
              <span>
                监控台只读；请在阶段工作台完整检查候选内容后提交决定。
              </span>
            </div>
          </div>
        ) : null}

        <div className="phase32-monitor-content-scroll">
          <Phase32RunArtifactPreview
            artifact={artifactState.artifact}
            error={artifactState.error}
            loading={artifactState.loading}
            onReload={artifactState.reload}
            refreshing={artifactState.refreshing}
            stageLabel={selectedStage?.label ?? "阶段"}
            unitRef={selectedUnitRef}
          />
        </div>
      </main>

      <Phase32RunMonitorInspector
        connection={runConnection}
        events={runEvents}
        onClose={() => setInspectorOpen(false)}
        open={inspectorOpen}
        returnFocusRef={inspectorTriggerRef}
        run={activeRun}
      />
    </div>
  )
}

type MetricProps = {
  label: string
  value: string
}

function Metric({ label, value }: MetricProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function unitizationLabel(stage: Phase32RouteStageManifest | undefined) {
  if (!stage) return "-"
  if (stage.unitization === "aggregate") return "聚合阶段"
  if (stage.unitization === "bounded_units") return "有界单元"
  if (stage.unitization === "sequential_units") return "顺序单元"
  return "确定性交付"
}

function stageStatusLabel(value: string) {
  if (value === "locked") return "锁定"
  if (value === "available") return "可开始"
  if (value === "running") return "运行中"
  if (value === "awaiting_decision") return "等待决策"
  if (value === "completed") return "已提交"
  if (value === "failed") return "异常"
  return value
}

function runStatusLabel(value: string) {
  if (value === "created") return "待启动"
  if (value === "running") return "运行中"
  if (value === "awaiting_decision") return "待决策"
  if (value === "image_deferred") return "图片验收暂缓"
  if (value === "completed") return "已完成"
  if (value === "failed") return "运行失败"
  if (value === "cancelled") return "已取消"
  return value
}
