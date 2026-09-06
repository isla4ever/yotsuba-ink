import { useEffect, useMemo, useRef, useState } from "react"
import { Check, ChevronLeft, ChevronRight, Lock } from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import type { CreationIntentDraft } from "../contracts/creationWizard"
import { projectPresentation } from "../lib/projectPresentation"
import {
  CREATION_ROUTE_META,
  DEFAULT_CREATION_INTENT,
  matchWorkflows,
  routeForIntent,
  routeFromWorkflowId,
  routeMetaForIntent,
  intentError,
} from "../lib/creationWizard"
import { createProject } from "../services/projectApi"
import { useWorkflowTemplates } from "../state/useWorkflowTemplates"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { BookLoader } from "../layout/BookLoader"
import { CreationIntentStep } from "./CreationIntentStep"
import { WorkflowMatchStep } from "./WorkflowMatchStep"

const STEPS = [
  { label: "创作意图", desc: "类型、篇幅与目标规模" },
  { label: "匹配流水线", desc: "选择官方冻结配置" },
] as const

function intentForRoute(
  routeId: ReturnType<typeof routeForIntent>,
): CreationIntentDraft {
  if (!routeId) return DEFAULT_CREATION_INTENT
  return {
    ...DEFAULT_CREATION_INTENT,
    creationKind: routeId === "screenplay_sample" ? "screenplay" : "novel",
    novelLengthClass: routeId === "screenplay_sample" ? null : routeId,
    requestedTarget: CREATION_ROUTE_META[routeId].recommended,
  }
}

export default function CreationWizard() {
  const {
    creationWizardDraft,
    openProject,
    selectedTemplateId,
    setRoute,
    setCreationWizardDraft,
    setSelectedTemplateId,
  } = useApp()
  const { error, loading, refresh, workflows } = useWorkflowTemplates()
  const initialIntent = creationWizardDraft ?? DEFAULT_CREATION_INTENT
  const [intent, setIntent] = useState<CreationIntentDraft>(initialIntent)
  const [step, setStep] = useState(
    selectedTemplateId && !intentError(initialIntent) ? 1 : 0,
  )
  const [creatingProject, setCreatingProject] = useState(false)
  const [createError, setCreateError] = useState("")
  const seededFromTemplate = useRef(false)
  const projectCreationKey = useRef(newProjectCreationKey())
  const templateLoad = useLoadingPresence(loading && workflows.length === 0)

  useEffect(() => {
    setCreationWizardDraft(intent)
  }, [intent, setCreationWizardDraft])

  useEffect(() => {
    if (
      seededFromTemplate.current ||
      !selectedTemplateId ||
      workflows.length === 0
    )
      return
    const routeId = routeFromWorkflowId(selectedTemplateId, workflows)
    if (!routeId) return
    setIntent((current) => ({
      ...intentForRoute(routeId),
      creativeIntent: current.creativeIntent,
    }))
    seededFromTemplate.current = true
  }, [selectedTemplateId, workflows])

  const route = routeMetaForIntent(intent)
  const matches = useMemo(
    () => matchWorkflows(intent, workflows),
    [intent, workflows],
  )

  useEffect(() => {
    if (matches.length === 0) return
    if (
      selectedTemplateId &&
      matches.some((match) => match.workflow.id === selectedTemplateId)
    )
      return
    setSelectedTemplateId(matches[0].workflow.id)
  }, [matches, selectedTemplateId, setSelectedTemplateId])

  const selectedWorkflow = useMemo(
    () =>
      matches.find((match) => match.workflow.id === selectedTemplateId)
        ?.workflow ?? null,
    [matches, selectedTemplateId],
  )

  const handleIntentChange = (next: CreationIntentDraft) => {
    if (routeForIntent(next) !== routeForIntent(intent)) {
      setSelectedTemplateId(null)
    }
    setIntent(next)
    projectCreationKey.current = newProjectCreationKey()
    setCreateError("")
  }

  const handleWorkflowSelect = (workflowId: string) => {
    if (workflowId === selectedTemplateId) return
    setSelectedTemplateId(workflowId)
    projectCreationKey.current = newProjectCreationKey()
    setCreateError("")
  }

  const handleViewConfig = (workflowId: string) => {
    setSelectedTemplateId(workflowId)
    setRoute("workflow-template-detail")
  }

  const handleCreateProject = async () => {
    if (creatingProject || !selectedWorkflow || intentError(intent)) return
    setCreatingProject(true)
    setCreateError("")
    try {
      const project = await createProject({
        intent,
        workflowId: selectedWorkflow.id,
        idempotencyKey: projectCreationKey.current,
      })
      setSelectedTemplateId(null)
      openProject(projectPresentation(project), "brief")
      setCreationWizardDraft(null)
    } catch (reason) {
      setCreateError(reason instanceof Error ? reason.message : "创建作品失败")
    } finally {
      setCreatingProject(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 overflow-y-auto bg-base page-in">
      <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
        <header className="mb-7">
          <p className="mb-2 text-[10px] uppercase tracking-[0.16em] text-action">
            YOTSUBA INK · NEW WORK
          </p>
          <h1 className="text-xl font-semibold text-ink sm:text-2xl">
            新建作品
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ash">
            用两步把创作意图交给正确的生产链。流水线、模型和审核策略会在作品创建时冻结。
          </p>
        </header>

        <nav aria-label="新建作品步骤" className="mb-6 flex items-center">
          {STEPS.map((item, index) => (
            <div
              key={item.label}
              className="flex min-w-0 flex-1 items-center last:flex-none"
            >
              <button
                type="button"
                onClick={() => {
                  if (index === 0 || !intentError(intent)) setStep(index)
                }}
                className={`flex min-w-0 items-center gap-2 text-left transition-colors ${
                  step === index
                    ? "text-ink"
                    : index < step
                      ? "text-mint"
                      : "text-fog"
                }`}
              >
                <span
                  className={`grid size-7 shrink-0 place-items-center rounded-full border text-xs font-semibold transition-colors ${
                    step === index
                      ? "border-action bg-action text-white"
                      : index < step
                        ? "border-mint bg-mint-bg text-mint"
                        : "border-hairline text-fog"
                  }`}
                >
                  {index < step ? <Check size={13} /> : index + 1}
                </span>
                <span className="hidden min-w-0 sm:block">
                  <span className="block truncate text-xs">{item.label}</span>
                  <span className="block truncate text-[10px] text-fog">
                    {item.desc}
                  </span>
                </span>
              </button>
              {index < STEPS.length - 1 && (
                <span
                  className={`mx-2 h-px min-w-5 flex-1 ${
                    index < step ? "bg-mint" : "bg-hairline"
                  }`}
                  aria-hidden="true"
                />
              )}
            </div>
          ))}
        </nav>

        <main
          className="rounded-lg border border-hairline bg-surface p-4 shadow-[0_16px_50px_rgba(0,0,0,0.14)] sm:p-6"
          key={step}
        >
          {step === 0 && (
            <CreationIntentStep
              intent={intent}
              onChange={handleIntentChange}
              onNext={() => {
                if (!intentError(intent)) setStep(1)
              }}
            />
          )}
          {step === 1 && route && (
            <WorkflowMatchStep
              intent={intent}
              route={route}
              matches={matches}
              selectedWorkflow={selectedWorkflow}
              loading={loading || templateLoad.visible}
              error={error}
              createError={createError}
              onBack={() => setStep(0)}
              onSelect={handleWorkflowSelect}
              onConfigure={handleViewConfig}
              onCreateProject={() => void handleCreateProject()}
              onRefresh={() => void refresh()}
              creatingProject={creatingProject}
            />
          )}
        </main>

        {step === 1 && !route && (
          <div
            className="mt-4 rounded-lg border border-risk/30 bg-risk-bg p-4 text-sm text-risk"
            role="alert"
          >
            请返回第一步选择剧本或小说篇幅，再匹配对应流水线。
          </div>
        )}

        <div className="mt-5 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setStep(0)}
            disabled={step === 0}
            className="btn btn-secondary text-xs disabled:opacity-40"
          >
            <ChevronLeft size={13} /> 上一步
          </button>
          <span className="flex items-center gap-1.5 text-[10px] text-fog">
            <Lock size={10} />
            路线创建后不可切换
          </span>
          {step === 0 ? (
            <button
              type="button"
              onClick={() => {
                if (!intentError(intent)) setStep(1)
              }}
              className="btn btn-primary text-xs"
              disabled={Boolean(intentError(intent))}
            >
              下一步 <ChevronRight size={13} />
            </button>
          ) : (
            <span />
          )}
        </div>

        {templateLoad.visible && step === 0 && (
          <div className="pointer-events-none fixed inset-x-0 bottom-4 z-20 flex justify-center px-4">
            <BookLoader
              phase={templateLoad.exiting ? "exit" : "enter"}
              variant="compact"
              label="正在同步流水线目录"
              detail="准备路线匹配"
            />
          </div>
        )}
      </div>
    </div>
  )
}

function newProjectCreationKey() {
  const uuid = globalThis.crypto?.randomUUID?.()
  return `web-project-${uuid ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`}`
}
