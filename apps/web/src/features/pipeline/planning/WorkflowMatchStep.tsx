import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  GitBranch,
  Lock,
  Pencil,
  RefreshCw,
  Sparkles,
} from "lucide-react"
import type {
  CreationIntentDraft,
  CreationRouteMeta,
  WorkflowRouteMatch,
  CreationWorkflowCatalogItem,
} from "../contracts/creationWizard"
import {
  formatTarget,
  intentError,
  workflowDisplayName,
} from "../lib/creationWizard"
import { BookLoader } from "../layout/BookLoader"

function PipelineRibbon({
  route,
  workflowName,
}: {
  route: CreationRouteMeta
  workflowName: string
}) {
  return (
    <ol
      className="mt-3 flex min-w-0 items-center overflow-x-auto pb-1"
      aria-label={`${workflowName}阶段链`}
    >
      {route.stages.map((stage, index) => (
        <li key={stage} className="flex min-w-[62px] flex-1 items-center gap-1">
          <span className="grid size-6 shrink-0 place-items-center rounded-full border border-hairline bg-base font-mono text-[9px] text-action">
            {String(index + 1).padStart(2, "0")}
          </span>
          <span className="min-w-0 truncate text-[10px] text-ash" title={stage}>
            {stage}
          </span>
          {index < route.stages.length - 1 && (
            <span
              className="mx-1 h-px min-w-2 flex-1 bg-hairline"
              aria-hidden="true"
            />
          )}
        </li>
      ))}
    </ol>
  )
}

function WorkflowMatchCard({
  route,
  match,
  selected,
  onSelect,
  onConfigure,
}: {
  route: CreationRouteMeta
  match: WorkflowRouteMatch
  selected: boolean
  onSelect: () => void
  onConfigure: () => void
}) {
  const { workflow } = match
  const official = workflow.source === "official"
  const displayName = workflowDisplayName(workflow, route.id)
  return (
    <article
      className={`group rounded-lg border p-4 transition-[border-color,background-color,transform] duration-200 hover:-translate-y-0.5 ${
        selected
          ? "border-action/60 bg-action-bg"
          : "border-hairline bg-elev hover:border-action/30"
      }`}
    >
      <button
        type="button"
        className="w-full text-left outline-none"
        role="radio"
        aria-checked={selected}
        onClick={onSelect}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            onSelect()
          }
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className="badge badge-action">{route.shortLabel}</span>
              <span className="badge badge-ash">
                {official ? "官方推荐" : "自定义"}
              </span>
              {match.recommended && (
                <span className="badge badge-action">优先匹配</span>
              )}
            </div>
            <h3 className="truncate text-sm font-medium text-ink">
              {displayName}
            </h3>
            <p className="mt-1 text-[11px] leading-relaxed text-ash">
              {match.matchReason}
            </p>
          </div>
          <span
            className={`grid size-6 shrink-0 place-items-center rounded-full border ${
              selected
                ? "border-action bg-action text-white"
                : "border-hairline text-fog"
            }`}
          >
            {selected ? (
              <Check size={13} />
            ) : (
              <span className="size-1.5 rounded-full bg-hairline" />
            )}
          </span>
        </div>
        <PipelineRibbon route={route} workflowName={displayName} />
        <div className="mt-2 flex items-center gap-2 text-[10px] text-fog">
          <Bot size={10} className="text-action" />
          <span className="truncate">
            {route.stages.length} 个路线阶段；模型、预算与审阅策略在创建时冻结。
          </span>
        </div>
      </button>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-hairline/70 pt-3">
        <span className="flex items-center gap-1 text-[10px] text-fog">
          <Lock size={10} /> 创建后锁定
        </span>
        <button
          type="button"
          onClick={onConfigure}
          className="btn btn-ghost px-2 py-1 text-[10.5px]"
        >
          <Pencil size={10} /> 查看配置
        </button>
      </div>
    </article>
  )
}

export function WorkflowMatchStep({
  intent,
  route,
  matches,
  selectedWorkflow,
  loading,
  error,
  createError,
  onBack,
  onSelect,
  onConfigure,
  onCreateProject,
  onRefresh,
  creatingProject,
}: {
  intent: CreationIntentDraft
  route: CreationRouteMeta
  matches: WorkflowRouteMatch[]
  selectedWorkflow: CreationWorkflowCatalogItem | null
  loading: boolean
  error: string
  createError: string
  onBack: () => void
  onSelect: (id: string) => void
  onConfigure: (id: string) => void
  onCreateProject: () => void
  onRefresh: () => void
  creatingProject: boolean
}) {
  const validationError = intentError(intent)
  return (
    <section className="animate-fade-in" aria-labelledby="workflow-match-title">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] text-action">
            <GitBranch size={12} /> STEP 02 · 流水线匹配
          </p>
          <h2
            id="workflow-match-title"
            className="text-xl font-semibold text-ink"
          >
            为这次创作选择生产链
          </h2>
          <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ash">
            只展示与当前创作目标匹配的 canonical
            流水线。路线、阶段合同与审阅策略会一同冻结到 Run。
          </p>
        </div>
        <span className="hidden rounded-md border border-action/25 bg-action-bg px-2.5 py-1.5 text-[10px] text-action sm:inline-flex sm:items-center sm:gap-1.5">
          <Sparkles size={11} /> {route.label}
        </span>
      </div>

      <div className="mb-5 grid gap-3 rounded-lg border border-hairline bg-elev/70 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="badge badge-action">已锁定路线</span>
            <strong className="text-sm text-ink">{route.label}</strong>
            <span className="text-[10px] text-fog">
              {route.targetLabel}{" "}
              {formatTarget(
                intent.requestedTarget ?? route.recommended,
                route.unit,
              )}
            </span>
          </div>
          <p className="line-clamp-2 text-[11px] leading-relaxed text-ash">
            {intent.creativeIntent}
          </p>
        </div>
        <button
          type="button"
          onClick={onBack}
          className="btn btn-secondary justify-center text-xs"
        >
          <ArrowLeft size={12} /> 修改意图
        </button>
      </div>

      {error && (
        <div className="banner-warning mb-4 justify-between" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="btn btn-ghost px-2 py-1 text-[10px]"
            onClick={onRefresh}
          >
            <RefreshCw size={11} /> 重试
          </button>
        </div>
      )}
      {createError && (
        <div className="banner-warning mb-4" role="alert">
          {createError}
        </div>
      )}
      {validationError && (
        <div className="banner-warning mb-4" role="alert">
          {validationError}；请返回补全创作意图后再创建作品。
        </div>
      )}

      {loading && matches.length === 0 && (
        <BookLoader
          phase="enter"
          variant="compact"
          label="正在匹配路线流水线"
          detail="按创作意图同步 canonical 配置"
        />
      )}

      {!loading && matches.length === 0 && (
        <div className="rounded-lg border border-dashed border-hairline bg-elev/60 p-6 text-center">
          <p className="text-sm text-ink">当前路线目录不可用</p>
          <p className="mt-1 text-xs text-ash">
            请刷新 canonical 目录；系统不会回退到旧模板或猜测路线。
          </p>
          <button
            type="button"
            className="btn btn-secondary mt-4"
            onClick={onRefresh}
          >
            <RefreshCw size={13} /> 刷新目录
          </button>
        </div>
      )}

      {matches.length > 0 && (
        <div
          className="space-y-3"
          role="radiogroup"
          aria-label={`${route.label}匹配的流水线`}
        >
          {matches.map((match) => (
            <WorkflowMatchCard
              key={match.workflow.id}
              route={route}
              match={match}
              selected={match.workflow.id === selectedWorkflow?.id}
              onSelect={() => onSelect(match.workflow.id)}
              onConfigure={() => onConfigure(match.workflow.id)}
            />
          ))}
        </div>
      )}

      {selectedWorkflow && (
        <div className="mt-6 border-t border-hairline pt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-ink">准备创建作品</p>
              <p className="mt-0.5 text-[10px] text-fog">
                将以 {workflowDisplayName(selectedWorkflow, route.id)}
                作为冻结生产合同。
              </p>
            </div>
            <span className="badge badge-action">
              <Check size={10} className="mr-1" />
              已选择
            </span>
          </div>
          <button
            type="button"
            className="btn btn-primary w-full justify-center"
            disabled={creatingProject || Boolean(validationError)}
            onClick={onCreateProject}
          >
            <ArrowRight size={14} />{" "}
            {creatingProject ? "正在创建作品…" : "创建作品并进入 Brief"}
          </button>
        </div>
      )}
    </section>
  )
}
