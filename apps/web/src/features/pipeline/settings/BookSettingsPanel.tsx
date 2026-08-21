import { BookOpen, ExternalLink, Lock, Settings2, Workflow } from "lucide-react"
import { useApp } from "@/features/pipeline/state/PipelineAppProvider"
import { CollaborationRunBinding } from "./AuthorCollaborationSettings"

export function BookSettingsPanel() {
  const { activeProject, activeRun, setRoute, setSelectedTemplateId } = useApp()

  if (!activeProject) {
    return (
      <div className="flex-1 grid place-items-center p-6 page-in">
        <div className="text-center max-w-md">
          <Settings2 size={24} className="text-fog mx-auto mb-3" />
          <h1 className="text-sm font-semibold text-ink mb-1">没有打开作品</h1>
          <p className="text-xs text-fog">本书设置只在进入具体作品后显示。</p>
        </div>
      </div>
    )
  }

  const providerProfiles = activeRun
    ? [
        ...new Set(
          Object.values(activeRun.definition.provider_bindings).map(
            (binding) => binding.provider_profile_id,
          ),
        ),
      ]
    : []
  const models = activeRun
    ? [
        ...new Set(
          Object.values(activeRun.definition.provider_bindings).map(
            (binding) => binding.model,
          ),
        ),
      ]
    : []
  const openWorkflow = () => {
    setSelectedTemplateId(activeProject.workflowId)
    setRoute("workflow-template-detail")
  }

  const rows = [
    { label: "项目 ID", value: activeProject.id, mono: true },
    { label: "工作流", value: activeProject.workflowId, mono: true },
    {
      label: "当前 Run",
      value: activeProject.latestRunId || "尚未启动",
      mono: true,
    },
    { label: "创建时间", value: formatDate(activeProject.createdAt) },
    { label: "最后同步", value: formatDate(activeProject.updatedAt) },
    {
      label: "品质模式",
      value: activeRun
        ? modeLabel(activeRun.definition.quality_mode)
        : "将在 Run 创建时冻结",
    },
    { label: "文本模型", value: models.join(" / ") || "尚未冻结" },
    {
      label: "服务配置",
      value: providerProfiles.join(" / ") || "尚未冻结",
      mono: true,
    },
  ]

  return (
    <div className="flex-1 overflow-y-auto page-in">
      <header className="stage-aura border-b border-hairline bg-surface px-5 md:px-6 py-4 flex items-center gap-3">
        <BookOpen size={15} className="text-action" />
        <div>
          <h1 className="text-sm font-semibold text-ink">
            《{activeProject.title}》设置
          </h1>
          <p className="text-xs text-fog">
            项目身份、冻结工作流与 Provider 绑定
          </p>
        </div>
        <div className="flex-1" />
        <span className="badge badge-action">
          <Lock size={10} />
          Run 创建后只读
        </span>
      </header>

      <div className="max-w-3xl mx-auto p-4 md:p-6">
        <section className="mb-6">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <h2 className="text-xs font-semibold text-ink">生产配置</h2>
              <p className="text-[10px] text-fog mt-0.5">
                以下内容直接来自 Project 和当前 Run，不在创作过程中切换模式。
              </p>
            </div>
            <button
              type="button"
              className="btn btn-secondary text-xs"
              onClick={openWorkflow}
            >
              <Workflow size={13} />
              查看流水线
              <ExternalLink size={11} />
            </button>
          </div>
          <div className="bg-surface border border-hairline rounded-lg overflow-hidden">
            {rows.map((row) => (
              <div
                key={row.label}
                className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 px-4 py-3 border-b border-ghost last:border-b-0"
              >
                <span className="text-xs text-fog sm:w-28 shrink-0">
                  {row.label}
                </span>
                <span
                  className={`text-xs text-ink font-medium break-all ${
                    row.mono ? "font-mono" : ""
                  }`}
                >
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-action-bg border border-action/25 rounded-lg p-4 flex items-start gap-3">
          <Lock size={14} className="text-action mt-0.5 shrink-0" />
          <div>
            <strong className="text-xs text-ink">为何不能在这里修改模式</strong>
            <p className="text-xs text-ash leading-relaxed mt-1">
              Fast、Balanced、Deep 和每个阶段的 Provider 绑定属于 Run
              的冻结生产合同。需要更换时，应从创作台复制或编辑工作流，再创建新的作品或
              Run，避免历史 Artifact 与生成条件失配。
            </p>
          </div>
        </section>

        <div className="mt-6">
          <CollaborationRunBinding run={activeRun} />
        </div>
      </div>
    </div>
  )
}

function modeLabel(mode: "fast" | "balanced" | "deep") {
  return ({
    fast: "极速 Fast",
    balanced: "均衡 Balanced",
    deep: "精细 Deep",
  } as const)[mode]
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN")
}
