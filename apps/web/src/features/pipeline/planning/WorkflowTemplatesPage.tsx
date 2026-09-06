import {
  ArrowRight,
  Bot,
  Check,
  ChevronRight,
  GitBranch,
  Plus,
  RefreshCw,
  Settings2,
} from "lucide-react"
import type { CreationWorkflowCatalogItem } from "../contracts/creationWizard"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { BookLoader } from "../layout/BookLoader"
import { useWorkflowTemplates } from "../state/useWorkflowTemplates"

function FlowPipeline({ workflow }: { workflow: CreationWorkflowCatalogItem }) {
  return (
    <div className="min-w-0 px-4 py-3.5">
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-[10.5px] font-medium text-ash">
          <GitBranch size={11} className="text-action" />
          {workflow.stages.length} 阶段 canonical 生产链
        </span>
        <span className="truncate text-right font-mono text-[9.5px] text-fog">
          {workflow.revision} · {workflow.exportProfiles.join(" / ")}
        </span>
      </div>

      <div className="workflow-pipeline-scroll overflow-x-auto overflow-y-hidden px-0.5 pt-0.5 pb-1 [scrollbar-gutter:stable] [scrollbar-width:thin] max-md:snap-x max-md:snap-proximity">
        <ol
          className="workflow-pipeline-track m-0 flex min-w-[592px] list-none p-0 max-md:min-w-[672px]"
          aria-label={`${workflow.name}${workflow.stages.length}阶段生产链`}
        >
          {workflow.stages.map((stage, index) => (
            <li
              key={stage.stageId}
              className="relative flex min-w-0 flex-[1_0_74px] snap-center flex-col items-center text-center max-md:basis-[84px]"
              title={`${stage.label} · ${stage.artifactKind}`}
            >
              <span
                aria-hidden="true"
                className="absolute top-[17px] h-px bg-hairline"
                style={{
                  left: index === 0 ? "50%" : 0,
                  right: index === workflow.stages.length - 1 ? "50%" : 0,
                }}
              />
              <span className="workflow-pipeline-marker relative z-[1] flex size-[35px] items-center justify-center rounded-full border border-action/45 bg-base font-mono text-[9px] tabular-nums text-action">
                {String(index + 1).padStart(2, "0")}
              </span>
              <strong className="mt-1.5 text-[10.5px] font-medium text-ink">
                {stage.label}
              </strong>
              <span className="flex max-w-[calc(100%-7px)] min-w-0 items-center justify-center gap-[3px] font-mono text-[8px] text-fog">
                {stage.providerTaskKind ? (
                  <Bot
                    size={9}
                    aria-hidden="true"
                    className="shrink-0 text-action"
                  />
                ) : (
                  <Check
                    size={9}
                    aria-hidden="true"
                    className="shrink-0 text-mint"
                  />
                )}
                <span className="truncate">{stage.artifactKind}</span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}

function TemplateRow({
  workflow,
  onDetail,
  onUse,
}: {
  workflow: CreationWorkflowCatalogItem
  onDetail: () => void
  onUse: () => void
}) {
  return (
    <article className="group flex shrink-0 flex-col border-b border-ghost bg-surface transition-colors duration-150 last:border-b-0 hover:bg-hover/30 xl:flex-row">
      <button
        type="button"
        onClick={onDetail}
        aria-label={`查看${workflow.name}配置`}
        className="flex min-w-0 flex-1 flex-col text-left outline-none focus-visible:bg-hover/60 xl:flex-row"
      >
        <div className="min-w-0 border-l-2 border-action px-4 py-3.5 xl:w-72 xl:shrink-0">
          <div className="mb-2 flex items-center gap-2">
            <span className="badge badge-action">官方路线</span>
            <span className="badge badge-ash">{workflow.revision}</span>
            <ChevronRight
              size={12}
              className="ml-auto text-fog transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-ink"
            />
          </div>
          <h2 className="truncate text-[13px] font-semibold text-ink">
            {workflow.name}
          </h2>
          <p className="mt-1 line-clamp-2 text-[10.5px] leading-relaxed text-ash">
            {workflow.summary}
          </p>
          <div className="mt-2.5 flex items-center gap-2 text-[9.5px] text-fog">
            <span>{workflow.deliverableKind}</span>
            <span aria-hidden="true">·</span>
            <span>{workflow.reviewPolicy.checkpointPolicy}</span>
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
          <Settings2 size={11} /> 查看配置
        </button>
        <button
          type="button"
          onClick={onUse}
          className="btn btn-primary min-w-0 flex-1 justify-center px-3 py-1.5 text-[10.5px] xl:w-full xl:flex-none"
        >
          使用此路线 <ArrowRight size={11} />
        </button>
      </div>
    </article>
  )
}

export default function WorkflowTemplatesPage({
  onDetail,
  onUseTemplate,
  onCreateProject,
}: {
  onDetail: (id: string) => void
  onUseTemplate: (id: string) => void
  onCreateProject?: () => void
}) {
  const { error, loading, refresh, workflows } = useWorkflowTemplates()
  const initialLoad = useLoadingPresence(loading && workflows.length === 0)

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-base page-in">
      <div className="flex items-end justify-between gap-6 border-b border-hairline bg-surface px-5 py-4 md:px-6">
        <div className="min-w-0">
          <h1 className="mb-1 text-base font-semibold text-ink">
            三条官方创作路线
          </h1>
          <p className="text-sm text-ash">
            选择交付目标；阶段图、审阅策略和模型绑定会在创建作品后冻结
          </p>
        </div>
        {onCreateProject && (
          <button
            type="button"
            className="btn btn-action shrink-0 text-xs"
            onClick={onCreateProject}
          >
            <Plus size={13} /> 新建作品
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
        {error && (
          <div className="banner-warning mb-4 justify-between" role="alert">
            <span>{error}</span>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => void refresh()}
            >
              <RefreshCw size={12} /> 重试
            </button>
          </div>
        )}
        {initialLoad.visible ? (
          <BookLoader
            phase={initialLoad.exiting ? "exit" : "enter"}
            variant="panel"
            label="正在读取三路线目录"
            detail="同步 RouteSpec、ScaleProfile 与 ReviewPolicy"
          />
        ) : (
          <section
            className="overflow-hidden rounded-lg border border-hairline"
            aria-label="官方创作路线"
          >
            {workflows.map((workflow) => (
              <TemplateRow
                key={workflow.id}
                workflow={workflow}
                onDetail={() => onDetail(workflow.id)}
                onUse={() => onUseTemplate(workflow.id)}
              />
            ))}
          </section>
        )}
      </div>
    </div>
  )
}
