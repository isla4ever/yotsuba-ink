import { useEffect, useMemo, useState } from "react"
import {
  ArrowRight,
  Bot,
  Check,
  ChevronRight,
  Lock,
  RefreshCw,
  Settings2,
  Wand2,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import type { WorkflowDefinition } from "@/features/pipeline/contracts/workflow"
import { isOfficialWorkflowId } from "@/features/pipeline/lib/officialWorkflows"
import {
  qualityModeMeta,
  stageShortLabel,
  workflowDescription,
} from "@/features/pipeline/lib/workflowPresentation"
import { projectPresentation } from "@/features/pipeline/lib/projectPresentation"
import { createProject } from "@/features/pipeline/services/projectApi"
import { useWorkflowTemplates } from "@/features/pipeline/state/useWorkflowTemplates"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"

const STEPS = [
  { id: "workflow", label: "选择流水线", desc: "确定品质模式与八阶段配置" },
  { id: "idea", label: "提交创作想法", desc: "用一段自由文本说明要写的故事" },
]

function MiniPipeline({ workflow }: { workflow: WorkflowDefinition }) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto mt-2 pb-1">
      {workflow.nodes.map((node, index) => (
        <div key={node.id} className="flex items-center gap-0 shrink-0">
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] border bg-surface border-ghost text-ash">
            {node.provider_profile_id ? (
              <Bot size={7} className="text-balanced" />
            ) : (
              <Check size={7} className="text-fog" />
            )}
            <span>{stageShortLabel(node)}</span>
          </div>
          {index < workflow.nodes.length - 1 && (
            <ArrowRight size={8} className="text-fog/40 mx-0.5 shrink-0" />
          )}
        </div>
      ))}
    </div>
  )
}

function WorkflowOption({
  workflow,
  selected,
  onConfigure,
  onSelect,
}: {
  workflow: WorkflowDefinition
  selected: boolean
  onConfigure: () => void
  onSelect: () => void
}) {
  const mode = qualityModeMeta[workflow.quality_mode]
  return (
    <div
      className={`border rounded-lg p-3 transition-colors cursor-pointer ${
        selected
          ? "border-action/50 bg-action-bg"
          : "border-hairline bg-elev hover:border-action/30 hover:bg-hover"
      }`}
      onClick={onSelect}
      role="radio"
      aria-checked={selected}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onSelect()
        }
      }}
    >
      <div className="flex items-center justify-between gap-3 mb-0.5">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <span className="text-xs font-medium text-ink">{workflow.name}</span>
          <span className={`badge ${mode.badge} text-[10.5px]`}>
            {mode.label}
          </span>
          <span className="badge badge-ash text-[10.5px]">
            {isOfficialWorkflowId(workflow.id) ? "官方" : "自定义"}
          </span>
          <span className="font-mono text-[10.5px] text-fog truncate">
            {workflow.version}
          </span>
        </div>
        {selected ? (
          <Check size={13} className="text-action shrink-0" />
        ) : (
          <div className="w-4 h-4 rounded-full border border-hairline shrink-0" />
        )}
      </div>
      <p className="text-[10px] text-fog mb-1.5">
        {workflowDescription(workflow)}
      </p>
      <div className="flex items-end gap-2">
        <MiniPipeline workflow={workflow} />
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onConfigure()
          }}
          className="ml-auto text-[10.5px] text-fog hover:text-action transition-colors flex items-center gap-1 shrink-0 mb-1"
        >
          <Settings2 size={9} />
          配置
        </button>
      </div>
    </div>
  )
}

export default function PlanningPage() {
  const {
    openProject,
    selectedTemplateId,
    setMode,
    setRoute,
    setSelectedTemplateId,
  } = useApp()
  const { error, loading, refresh, workflows } = useWorkflowTemplates()
  const [step, setStep] = useState(0)
  const [idea, setIdea] = useState("")
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState("")
  const templateLoad = useLoadingPresence(loading && workflows.length === 0)

  useEffect(() => {
    if (selectedTemplateId || workflows.length === 0) return
    const preferred =
      workflows.find(
        (workflow) => workflow.id === "official-deepseek-balanced",
      ) ?? workflows[0]
    setSelectedTemplateId(preferred.id)
  }, [selectedTemplateId, setSelectedTemplateId, workflows])

  const chosenWorkflow = useMemo(
    () =>
      workflows.find((workflow) => workflow.id === selectedTemplateId) ?? null,
    [selectedTemplateId, workflows],
  )

  useEffect(() => {
    if (chosenWorkflow) setMode(chosenWorkflow.quality_mode)
  }, [chosenWorkflow, setMode])

  const handleViewConfig = (id: string) => {
    setSelectedTemplateId(id)
    setRoute("workflow-template-detail")
  }

  const handleCreateProject = async () => {
    if (creating || !chosenWorkflow || idea.trim().length < 20) return
    setCreating(true)
    setCreateError("")
    try {
      const project = await createProject({
        idea: idea.trim(),
        templateWorkflowId: chosenWorkflow.id,
        consumeWorkflowDraft: chosenWorkflow.id.startsWith("wf-once-"),
      })
      setSelectedTemplateId(null)
      openProject(projectPresentation(project), "brief")
    } catch (reason) {
      setCreateError(reason instanceof Error ? reason.message : "创建作品失败")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-base page-in">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-ink mb-1">
            新建小说 · 策划向导
          </h1>
          <p className="text-sm text-ash">
            先锁定生产流水线，再提交一段自由创作想法
          </p>
        </div>

        <div className="flex gap-0 mb-7 overflow-x-auto pb-1">
          {STEPS.map((item, index) => (
            <div
              key={item.id}
              className="flex items-center flex-1 last:flex-none"
            >
              <button
                type="button"
                onClick={() => {
                  if (index === 0 || chosenWorkflow) setStep(index)
                }}
                className={`flex items-center gap-2 min-w-[150px] transition-colors ${
                  step === index
                    ? "text-ink"
                    : index < step
                      ? "text-mint"
                      : "text-fog"
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center border-2 text-xs font-bold transition-colors ${
                    step === index
                      ? "border-mint bg-mint text-white"
                      : index < step
                        ? "border-mint bg-mint-bg text-mint"
                        : "border-hairline text-fog"
                  }`}
                >
                  {index < step ? <Check size={13} /> : index + 1}
                </div>
                <span className="text-left">
                  <span className="text-xs block">{item.label}</span>
                  <span className="text-[10.5px] text-fog block">
                    {item.desc}
                  </span>
                </span>
              </button>
              {index < STEPS.length - 1 && (
                <div
                  className={`h-px flex-1 min-w-6 mx-3 ${
                    index < step ? "bg-mint" : "bg-hairline"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        <div
          className="bg-surface border border-hairline rounded-lg p-6 animate-fade-in"
          key={step}
        >
          {step === 0 && (
            <div>
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-base font-medium text-ink mb-1">
                    选择制作流水线
                  </h2>
                  <p className="text-xs text-ash">
                    品质模式、Provider
                    与阶段参数会随作品冻结，创作过程中不可切换
                  </p>
                </div>
                <Lock size={14} className="text-fog shrink-0 mt-1" />
              </div>

              {error && (
                <div
                  className="banner-warning justify-between mb-3"
                  role="alert"
                >
                  <span>{error}</span>
                  <button
                    type="button"
                    className="btn btn-ghost text-xs py-1"
                    onClick={() => void refresh()}
                  >
                    <RefreshCw size={11} />
                    重试
                  </button>
                </div>
              )}
              {templateLoad.visible && (
                <BookLoader
                  phase={templateLoad.exiting ? "exit" : "enter"}
                  variant="compact"
                  label="正在读取工作流模板"
                  detail="准备可用于本书的冻结配置"
                />
              )}
              <div
                className={`space-y-2 max-h-[460px] overflow-y-auto ${
                  templateLoad.visible ? "hidden" : "animate-fade-in"
                }`}
                role="radiogroup"
                aria-label="工作流模板"
              >
                {workflows.map((workflow) => (
                  <WorkflowOption
                    key={workflow.id}
                    workflow={workflow}
                    selected={workflow.id === chosenWorkflow?.id}
                    onSelect={() => setSelectedTemplateId(workflow.id)}
                    onConfigure={() => handleViewConfig(workflow.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {step === 1 && (
            <div>
              <h2 className="text-base font-medium text-ink mb-1">
                提交创作想法
              </h2>
              <p className="text-xs text-ash mb-4">
                书名、类型、人物和结构都由 Brief
                生成并由你确认，这里只写想创作的故事
              </p>

              {chosenWorkflow && (
                <div className="mb-4 bg-action-bg border border-action/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Check size={12} className="text-action" />
                    <span className="text-xs font-medium text-action">
                      {chosenWorkflow.name}
                    </span>
                    <span
                      className={`badge ${qualityModeMeta[chosenWorkflow.quality_mode].badge}`}
                    >
                      {qualityModeMeta[chosenWorkflow.quality_mode].label}
                    </span>
                    <span className="text-[10px] text-fog">
                      <Lock size={9} className="inline mr-1" />
                      创建后锁定
                    </span>
                  </div>
                  <MiniPipeline workflow={chosenWorkflow} />
                </div>
              )}

              <label className="block">
                <span className="text-xs text-fog block mb-1.5">
                  自由创作想法
                </span>
                <textarea
                  className="input min-h-44 resize-y"
                  value={idea}
                  onChange={(event) => setIdea(event.target.value)}
                  placeholder="例如：近未来城市中，一名急救调度员每晚会接到来自 24 小时后的报警电话。他最初借此阻止事故，却逐渐发现每次干预都在改写一桩与自己家庭有关的旧案……"
                  autoFocus
                />
              </label>
              <div className="flex justify-between mt-2 text-[10px] text-fog">
                <span>至少 20 个字符；可写题材、氛围、禁忌和大致篇幅</span>
                <span className="font-mono">{idea.trim().length}</span>
              </div>

              {createError && (
                <div className="banner-warning mt-4" role="alert">
                  {createError}
                </div>
              )}
              <button
                type="button"
                className="btn btn-primary w-full mt-5 disabled:opacity-50"
                disabled={
                  creating || !chosenWorkflow || idea.trim().length < 20
                }
                onClick={() => void handleCreateProject()}
              >
                <Wand2 size={14} />{" "}
                {creating ? "正在创建作品…" : "创建作品并进入 Brief"}
              </button>
            </div>
          )}
        </div>

        <div className="flex justify-between mt-5">
          <button
            type="button"
            onClick={() => setStep(0)}
            disabled={step === 0}
            className="btn btn-secondary disabled:opacity-40"
          >
            上一步
          </button>
          {step === 0 && (
            <button
              type="button"
              onClick={() => setStep(1)}
              disabled={!chosenWorkflow}
              className="btn btn-primary disabled:opacity-40"
            >
              下一步 <ChevronRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
