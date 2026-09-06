import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  GitBranch,
  Lock,
  RefreshCw,
  ShieldCheck,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import type { CreationRouteStage } from "../contracts/creationWizard"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { useWorkflowTemplates } from "../state/useWorkflowTemplates"

const UNITIZATION_LABELS: Record<CreationRouteStage["unitization"], string> = {
  aggregate: "整体产物",
  bounded_units: "有界单元",
  sequential_units: "顺序单元",
  deterministic: "确定性交付",
}

export default function WorkflowTemplateDetailPage({
  templateId,
  onBack,
  onUse,
}: {
  templateId: string
  onBack: () => void
  onUse: (id: string) => void
}) {
  const { error, loading, refresh, workflows } = useWorkflowTemplates()
  const workflow = workflows.find((item) => item.id === templateId) ?? null
  const [activeStageId, setActiveStageId] = useState("")
  const activeStage = useMemo(
    () =>
      workflow?.stages.find((stage) => stage.stageId === activeStageId) ??
      workflow?.stages[0] ??
      null,
    [activeStageId, workflow],
  )
  const initialLoad = useLoadingPresence(loading && !workflow)

  useEffect(() => {
    if (!workflow) return
    if (!workflow.stages.some((stage) => stage.stageId === activeStageId)) {
      setActiveStageId(workflow.stages[0]?.stageId ?? "")
    }
  }, [activeStageId, workflow])

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在展开路线合同"
        detail="读取 RouteSpec、ScaleProfile 与 ReviewPolicy"
      />
    )
  }

  if (!workflow || !activeStage) {
    return (
      <div className="grid flex-1 place-items-center p-6">
        <div className="w-full max-w-md rounded-lg border border-hairline bg-surface p-5 text-center">
          <p className="mb-3 text-sm text-ink">
            {error || "该 canonical 路线不存在"}
          </p>
          <div className="flex justify-center gap-2">
            <button
              type="button"
              onClick={onBack}
              className="btn btn-secondary text-xs"
            >
              <ArrowLeft size={12} /> 返回
            </button>
            <button
              type="button"
              onClick={() => void refresh()}
              className="btn btn-primary text-xs"
            >
              <RefreshCw size={12} /> 重试
            </button>
          </div>
        </div>
      </div>
    )
  }

  const activeIndex = workflow.stages.indexOf(activeStage)
  const mandatory = workflow.reviewPolicy.mandatoryDecisionStages.includes(
    activeStage.stageId,
  )
  const autoContinue = workflow.reviewPolicy.autoContinueStages.includes(
    activeStage.stageId,
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-base page-in">
      <header className="stage-aura flex flex-wrap items-center gap-3 border-b border-hairline bg-surface px-4 py-4 md:px-6">
        <button
          type="button"
          onClick={onBack}
          className="btn btn-ghost p-1.5"
          aria-label="返回官方路线"
        >
          <ArrowLeft size={14} />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-base font-semibold text-ink">
              {workflow.name}
            </h1>
            <span className="badge badge-action">官方 canonical</span>
            <span className="badge badge-ash">{workflow.revision}</span>
          </div>
          <p className="mt-1 text-xs text-ash">
            {workflow.summary}；创建后按 digest 冻结，不接受运行中切换。
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary text-xs"
          onClick={() => onUse(workflow.id)}
        >
          使用此路线 <ArrowRight size={12} />
        </button>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)]">
        <main className="min-h-0 overflow-y-auto border-b border-hairline p-4 md:p-6 lg:border-b-0 lg:border-r">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-action">
                RouteSpec
              </p>
              <h2 className="mt-1 text-sm font-semibold text-ink">
                {workflow.stages.length} 阶段生产链
              </h2>
            </div>
            <span className="font-mono text-[10px] text-fog">
              {workflow.id}
            </span>
          </div>
          <ol className="space-y-2" aria-label={`${workflow.name}阶段合同`}>
            {workflow.stages.map((stage, index) => {
              const selected = stage.stageId === activeStage.stageId
              return (
                <li key={stage.stageId}>
                  <button
                    type="button"
                    onClick={() => setActiveStageId(stage.stageId)}
                    aria-current={selected ? "step" : undefined}
                    className={`grid w-full grid-cols-[34px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border p-3 text-left transition-colors ${
                      selected
                        ? "border-action/50 bg-action-bg"
                        : "border-hairline bg-surface hover:border-action/25 hover:bg-hover/40"
                    }`}
                  >
                    <span
                      className={`grid size-8 place-items-center rounded-full border font-mono text-[10px] ${
                        selected
                          ? "border-action text-action"
                          : "border-hairline text-fog"
                      }`}
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="min-w-0">
                      <strong className="block truncate text-xs font-medium text-ink">
                        {stage.label}
                      </strong>
                      <span className="block truncate font-mono text-[9.5px] text-fog">
                        {stage.artifactKind}
                      </span>
                    </span>
                    {stage.providerTaskKind ? (
                      <Bot size={13} className="text-action" />
                    ) : (
                      <Check size={13} className="text-mint" />
                    )}
                  </button>
                </li>
              )
            })}
          </ol>
        </main>

        <aside
          className="min-h-0 overflow-y-auto bg-surface p-4 md:p-6"
          aria-label={`${activeStage.label}阶段合同`}
        >
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-action">
                阶段 {String(activeIndex + 1).padStart(2, "0")}
              </p>
              <h2 className="mt-1 text-base font-semibold text-ink">
                {activeStage.label}
              </h2>
            </div>
            <span className="badge badge-ash">
              {UNITIZATION_LABELS[activeStage.unitization]}
            </span>
          </div>

          <dl className="overflow-hidden rounded-lg border border-hairline bg-base text-xs">
            <MetaRow label="Artifact" value={activeStage.artifactKind} mono />
            <MetaRow label="工作台" value={activeStage.workbenchKind} mono />
            <MetaRow
              label="Provider 任务"
              value={activeStage.providerTaskKind ?? "系统确定性执行"}
              mono
            />
            <MetaRow
              label="上游依赖"
              value={activeStage.upstreamStageIds.join(" / ") || "无"}
              mono
            />
            <MetaRow
              label="作者决策"
              value={
                mandatory
                  ? "必须确认"
                  : autoContinue
                    ? "策略允许自动继续"
                    : "按阶段策略"
              }
            />
            <MetaRow
              label="作者协作"
              value={activeStage.collaborationEnabled ? "可用" : "不开放"}
            />
          </dl>

          <section className="mt-5 rounded-lg border border-action/25 bg-action-bg p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-ink">
              <ShieldCheck size={13} className="text-action" /> 冻结边界
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ash">
              Context、决策策略、Artifact 类型和 Provider binding 在 Run
              创建时共同冻结。模型配置不在路线间做隐式 fallback。
            </p>
            <div className="mt-3 flex items-center gap-2 font-mono text-[9px] text-fog">
              <Lock size={10} /> {workflow.workflowDigest.slice(0, 20)}…
            </div>
          </section>

          <section className="mt-4 rounded-lg border border-hairline bg-base p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-ink">
              <GitBranch size={13} className="text-action" /> 交付与规模
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ash">
              {workflow.scalePolicy.rationale}
            </p>
            <p className="mt-2 font-mono text-[10px] text-fog">
              {workflow.exportProfiles.join(" / ")} ·{" "}
              {workflow.scalePolicy.minimum}–{workflow.scalePolicy.maximum}{" "}
              {workflow.scalePolicy.unit}
            </p>
          </section>
        </aside>
      </div>
    </div>
  )
}

function MetaRow({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="grid grid-cols-[92px_minmax(0,1fr)] gap-3 border-b border-ghost px-3 py-2.5 last:border-b-0">
      <dt className="text-fog">{label}</dt>
      <dd
        className={`break-words text-ink ${
          mono ? "font-mono text-[10px]" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  )
}
