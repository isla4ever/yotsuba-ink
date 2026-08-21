import {
  ArrowRight,
  Bot,
  Check,
  ChevronRight,
  Clock,
  GitBranch,
  RefreshCw,
  Settings2,
  Trash2,
} from "lucide-react"
import type { CSSProperties } from "react"
import type { WorkflowDefinition } from "@/features/pipeline/contracts/workflow"
import { isOfficialWorkflowId } from "@/features/pipeline/lib/officialWorkflows"
import {
  qualityModeMeta,
  stageShortLabel,
  workflowBadges,
  workflowDescription,
  workflowProviderName,
} from "@/features/pipeline/lib/workflowPresentation"
import { useWorkflowTemplates } from "@/features/pipeline/state/useWorkflowTemplates"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"

function FlowPipeline({ workflow }: { workflow: WorkflowDefinition }) {
  const generatedCount = workflow.nodes.filter((node) =>
    Boolean(node.provider_profile_id),
  ).length
  const models = [
    ...new Set(
      workflow.nodes.map((node) => node.model_settings.model).filter(Boolean),
    ),
  ]

  return (
    <div
      className="min-w-0 px-4 py-3.5"
      style={
        {
          "--workflow-accent": `var(--accent-${workflow.quality_mode})`,
        } as CSSProperties
      }
    >
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-[10.5px] font-medium text-ash">
          <GitBranch size={11} className="text-action" />
          八阶段生产链
        </span>
        <span className="truncate text-right font-mono text-[9.5px] text-fog">
          {generatedCount} AI · {models.length || 1} MODEL
        </span>
      </div>

      <div className="workflow-pipeline-scroll overflow-x-auto overflow-y-hidden px-0.5 pt-0.5 pb-1 [scrollbar-gutter:stable] [scrollbar-width:thin] max-md:snap-x max-md:snap-proximity">
        <ol
          className="workflow-pipeline-track m-0 flex min-w-[592px] list-none p-0 max-md:min-w-[672px]"
          aria-label={`${workflow.name}八阶段生产链`}
        >
          {workflow.nodes.map((node, index) => {
            const terminal = index === 0 || index === workflow.nodes.length - 1
            return (
              <li
                key={node.id}
                className="relative flex min-w-0 flex-[1_0_74px] snap-center flex-col items-center text-center max-md:basis-[84px]"
                title={`${node.label} · ${workflowProviderName(workflow, node)} · ${node.model_settings.model || "系统任务"}`}
              >
                <span
                  aria-hidden="true"
                  className="absolute top-[17px] h-px opacity-65"
                  style={{
                    background:
                      "color-mix(in srgb, var(--workflow-accent) 58%, var(--border-hl))",
                    left: index === 0 ? "50%" : 0,
                    right: index === workflow.nodes.length - 1 ? "50%" : 0,
                  }}
                />
                <span
                  className="workflow-pipeline-marker relative z-[1] flex size-[35px] items-center justify-center rounded-full border bg-base font-mono text-[9px] tabular-nums"
                  aria-hidden="true"
                  style={{
                    borderColor: `color-mix(in srgb, var(--workflow-accent) ${
                      terminal ? 70 : 48
                    }%, var(--border-hl))`,
                    color: terminal
                      ? "var(--workflow-accent)"
                      : "var(--text-ash)",
                  }}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                </span>
                <strong className="mt-1.5 text-[10.5px] font-medium text-ink">
                  {stageShortLabel(node)}
                </strong>
                <span className="flex max-w-[calc(100%-7px)] min-w-0 items-center justify-center gap-[3px] font-mono text-[8px] text-fog">
                  {node.provider_profile_id ? (
                    <Bot
                      size={9}
                      aria-hidden="true"
                      className="shrink-0 text-[var(--workflow-accent)]"
                    />
                  ) : (
                    <Check
                      size={9}
                      aria-hidden="true"
                      className="shrink-0 text-[var(--workflow-accent)]"
                    />
                  )}
                  <span className="truncate">
                    {node.model_settings.model || "system"}
                  </span>
                </span>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}

function TemplateRow({
  workflow,
  onDetail,
  onUse,
  onDelete,
}: {
  workflow: WorkflowDefinition
  onDetail: () => void
  onUse: () => void
  onDelete: () => void
}) {
  const mode = qualityModeMeta[workflow.quality_mode]
  const official = isOfficialWorkflowId(workflow.id)

  return (
    <article className="group flex shrink-0 flex-col border-b border-ghost bg-surface transition-colors duration-150 last:border-b-0 hover:bg-hover/30 xl:flex-row">
      <button
        type="button"
        onClick={onDetail}
        aria-label={`${official ? "查看" : "编辑"}${workflow.name}配置`}
        className="flex min-w-0 flex-1 flex-col text-left outline-none focus-visible:bg-hover/60 xl:flex-row"
      >
        <div
          className="min-w-0 border-l-2 px-4 py-3.5 xl:w-72 xl:shrink-0"
          style={{
            borderLeftColor: `var(--accent-${workflow.quality_mode})`,
          }}
        >
          <div className="mb-2 flex items-center gap-2">
            <span className={`badge ${mode.badge}`}>{mode.label}</span>
            {workflowBadges(workflow)
              .filter((badge) => badge !== mode.label)
              .map((badge) => (
                <span key={badge} className="badge badge-ash">
                  {badge}
                </span>
              ))}
            <ChevronRight
              size={12}
              className="ml-auto text-fog transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-ink"
            />
          </div>
          <h2 className="truncate text-[13px] font-semibold text-ink">
            {workflow.name}
          </h2>
          <p className="mt-1 line-clamp-2 text-[10.5px] leading-relaxed text-ash">
            {workflowDescription(workflow)}
          </p>
          <div className="mt-2.5 flex items-center gap-2 text-[9.5px] text-fog">
            <span>Phase 27</span>
            <span aria-hidden="true">·</span>
            <span
              className="min-w-0 truncate font-mono"
              title={workflow.version}
            >
              {workflow.version}
            </span>
          </div>
        </div>

        <div className="min-w-0 flex-1 border-t border-ghost xl:border-l xl:border-t-0">
          <FlowPipeline workflow={workflow} />
        </div>
      </button>

      <div className="flex items-center gap-2 border-t border-ghost bg-elev/55 px-3 py-3 xl:w-44 xl:shrink-0 xl:flex-col xl:justify-center xl:border-l xl:border-t-0">
        <button
          type="button"
          onClick={onDetail}
          className="btn btn-secondary min-w-0 flex-1 justify-center px-3 py-1.5 text-[10.5px] xl:w-full xl:flex-none"
        >
          <Settings2 size={11} /> {official ? "查看配置" : "编辑配置"}
        </button>
        {!official && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm(`确认删除工作流模板“${workflow.name}”吗？`))
                onDelete()
            }}
            className="btn btn-ghost px-2 py-1.5 text-fog hover:text-risk"
            title="删除模板"
            aria-label={`删除${workflow.name}`}
          >
            <Trash2 size={11} />
          </button>
        )}
        <button
          type="button"
          onClick={onUse}
          className="btn btn-primary min-w-0 flex-1 justify-center px-3 py-1.5 text-[10.5px] xl:w-full xl:flex-none"
        >
          使用此流程 <ArrowRight size={11} />
        </button>
      </div>
    </article>
  )
}

export default function WorkflowTemplatesPage({
  onDetail,
  onUseTemplate,
}: {
  onDetail: (id: string) => void
  onUseTemplate: (id: string) => void
}) {
  const { error, loading, refresh, remove, workflows } = useWorkflowTemplates()
  const initialLoad = useLoadingPresence(loading && workflows.length === 0)
  const officialCount = workflows.filter((workflow) =>
    isOfficialWorkflowId(workflow.id),
  ).length

  return (
    <div className="flex flex-1 min-h-0 min-w-0 flex-col overflow-hidden bg-base page-in">
      <div className="flex items-end justify-between gap-6 border-b border-hairline bg-surface px-5 py-4 md:px-6">
        <div className="min-w-0">
          <h1 className="mb-1 text-base font-semibold text-ink">工作流模板</h1>
          <p className="text-sm text-ash">
            选择八阶段制作流程；创建作品后模式、模型与阶段参数会锁定
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-fog">
            <span className="flex items-center gap-1.5">
              <Bot size={11} className="text-balanced" />
              真实 Provider 绑定
            </span>
            <span className="flex items-center gap-1.5">
              <Clock size={11} />
              真实版本号
            </span>
          </div>
        </div>
        <dl className="hidden shrink-0 grid-cols-3 overflow-hidden rounded-md border border-ghost bg-base md:grid">
          <div className="border-r border-ghost px-4 py-2 text-center">
            <dt className="text-[9px] text-fog">全部</dt>
            <dd className="mt-0.5 font-mono text-xs text-ink">
              {workflows.length}
            </dd>
          </div>
          <div className="border-r border-ghost px-4 py-2 text-center">
            <dt className="text-[9px] text-fog">官方</dt>
            <dd className="mt-0.5 font-mono text-xs text-mint">
              {officialCount}
            </dd>
          </div>
          <div className="px-4 py-2 text-center">
            <dt className="text-[9px] text-fog">自定义</dt>
            <dd className="mt-0.5 font-mono text-xs text-ink">
              {workflows.length - officialCount}
            </dd>
          </div>
        </dl>
      </div>

      <div className="flex flex-1 min-h-0 flex-col overflow-y-auto p-4 md:p-6">
        {error && (
          <div className="banner-warning mb-4 justify-between" role="alert">
            <span>{error}</span>
            <button
              type="button"
              className="btn btn-ghost py-1 text-xs"
              onClick={() => void refresh()}
            >
              <RefreshCw size={12} /> 重试
            </button>
          </div>
        )}

        {initialLoad.visible && (
          <BookLoader
            phase={initialLoad.exiting ? "exit" : "enter"}
            variant="panel"
            label="正在读取工作流模板"
            detail="同步官方与自定义八阶段流水线"
          />
        )}

        {!initialLoad.visible && workflows.length === 0 && !error && (
          <div className="grid min-h-60 shrink-0 place-items-center rounded-lg border border-hairline bg-surface p-6 text-sm text-fog">
            暂无可用于新建作品的模板。
          </div>
        )}

        {!initialLoad.visible && workflows.length > 0 && (
          <section
            className="shrink-0 overflow-hidden rounded-lg border border-hairline bg-surface"
            aria-label="工作流模板目录"
          >
            <header className="flex items-center justify-between gap-4 border-b border-hairline bg-elev px-4 py-3">
              <div className="flex min-w-0 items-center gap-2">
                <GitBranch size={13} className="text-action" />
                <strong className="text-[11px] font-semibold text-ink">
                  流水线目录
                </strong>
                <span className="truncate text-[10px] text-fog">
                  点击模板主体直接查看或编辑阶段配置
                </span>
              </div>
              <span className="shrink-0 font-mono text-[10px] text-fog">
                {workflows.length} PIPELINES
              </span>
            </header>

            {workflows.map((workflow) => (
              <TemplateRow
                key={workflow.id}
                workflow={workflow}
                onDetail={() => onDetail(workflow.id)}
                onUse={() => onUseTemplate(workflow.id)}
                onDelete={() => void remove(workflow.id)}
              />
            ))}
          </section>
        )}
      </div>
    </div>
  )
}
