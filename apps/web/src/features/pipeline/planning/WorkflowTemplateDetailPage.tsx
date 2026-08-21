import { useEffect, useMemo, useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  Copy,
  Lock,
  RefreshCw,
  Save,
  Settings2,
} from "lucide-react"
import type {
  QualityMode,
  WorkflowDefinition,
  WorkflowStage,
} from "@/features/pipeline/contracts/workflow"
import { isOfficialWorkflowId } from "@/features/pipeline/lib/officialWorkflows"
import {
  qualityModeMeta,
  stageShortLabel,
  workflowDescription,
  workflowProviderName,
} from "@/features/pipeline/lib/workflowPresentation"
import { WorkflowStageDeck } from "@/features/pipeline/planning/WorkflowStageDeck"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import {
  duplicateWorkflowDefinition,
  getWorkflowDefinition,
  saveWorkflowDefinition,
} from "@/features/pipeline/services/workflowApi"

const STAGE_DESCRIPTIONS: Record<string, string> = {
  brief: "冻结故事承诺、最少世界规则、主题、结局方向、叙事声音与篇幅包络。",
  spine: "生成确定数量的因果推进节点、里程碑、结局与有限开放问题。",
  cast: "根据故事脊柱冻结具名主体、职责、边界、出场窗口与关系。",
  volumes: "划定自然分卷边界，并生成每卷承诺、冲突、高潮与收束。",
  detail: "按冻结章节槽位生成场景目标、冲突、转折、结果与跨章交接。",
  text: "按场景顺序生成章节正文，并进入审稿、作者决策与证据写回。",
  cover: "生成可执行封面 brief、图片提示词与候选资产。",
  export: "汇总已接受版本、封面和元数据，生成不可变导出收据。",
}

export default function WorkflowTemplateDetailPage({
  templateId,
  onBack,
  onOpen,
  onUse,
}: {
  templateId: string
  onBack: () => void
  onOpen: (id: string) => void
  onUse: (id: string) => void
}) {
  const [workflow, setWorkflow] = useState<WorkflowDefinition | null>(null)
  const [activeStageId, setActiveStageId] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [actionState, setActionState] =
    useState<"idle" | "saving" | "saved" | "copying">("idle")

  const load = async (signal?: AbortSignal) => {
    setLoading(true)
    try {
      const nextWorkflow = await getWorkflowDefinition(templateId, signal)
      setWorkflow(nextWorkflow)
      setActiveStageId((current) =>
        nextWorkflow.nodes.some((stage) => stage.id === current)
          ? current
          : (nextWorkflow.nodes[0]?.id ?? ""),
      )
      setError("")
    } catch (reason) {
      if (signal?.aborted) return
      setError(reason instanceof Error ? reason.message : "工作流配置读取失败")
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [templateId])

  const official = workflow ? isOfficialWorkflowId(workflow.id) : false
  const activeStage =
    workflow?.nodes.find((stage) => stage.id === activeStageId) ??
    workflow?.nodes[0]
  const activeIndex =
    activeStage && workflow ? workflow.nodes.indexOf(activeStage) : 0
  const models = useMemo(
    () =>
      workflow
        ? [
            ...new Set(
              workflow.nodes
                .map((stage) => stage.model_settings.model)
                .filter(Boolean),
            ),
          ]
        : [],
    [workflow],
  )
  const initialLoad = useLoadingPresence(loading && !workflow)

  const updateWorkflow = (nextWorkflow: WorkflowDefinition) => {
    setWorkflow(nextWorkflow)
    setActionState("idle")
  }

  const updateStage = (nextStage: WorkflowStage) => {
    if (!workflow) return
    updateWorkflow({
      ...workflow,
      nodes: workflow.nodes.map((stage) =>
        stage.id === nextStage.id ? nextStage : stage,
      ),
    })
  }

  const handleSave = async () => {
    if (!workflow || official) return
    setActionState("saving")
    try {
      setWorkflow(await saveWorkflowDefinition(workflow))
      setActionState("saved")
      setError("")
    } catch (reason) {
      setActionState("idle")
      setError(reason instanceof Error ? reason.message : "工作流保存失败")
    }
  }

  const handleCopy = async () => {
    if (!workflow) return
    setActionState("copying")
    try {
      const copied = await duplicateWorkflowDefinition(workflow.id, {
        name: `${workflow.name} 自定义副本`,
        is_template: true,
      })
      setError("")
      onOpen(copied.id)
    } catch (reason) {
      setActionState("idle")
      setError(reason instanceof Error ? reason.message : "工作流复制失败")
    }
  }

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在展开流水线"
        detail="读取八阶段配置与 Provider 绑定"
      />
    )
  }

  if (!workflow || !activeStage) {
    return (
      <div className="flex-1 grid place-items-center p-6">
        <div className="max-w-md w-full bg-surface border border-hairline rounded-lg p-5 text-center">
          <p className="text-sm text-ink mb-3">{error || "该工作流不存在"}</p>
          <div className="flex justify-center gap-2">
            <button
              type="button"
              onClick={onBack}
              className="btn btn-secondary text-xs"
            >
              <ArrowLeft size={12} />
              返回
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="btn btn-primary text-xs"
            >
              <RefreshCw size={12} />
              重试
            </button>
          </div>
        </div>
      </div>
    )
  }

  const mode = qualityModeMeta[workflow.quality_mode]

  return (
    <div className="workflow-detail-page page-in">
      <header className="workflow-detail-header stage-aura">
        <button
          type="button"
          onClick={onBack}
          className="btn btn-ghost p-1.5"
          aria-label="返回工作流模板"
        >
          <ArrowLeft size={14} />
        </button>
        <div className="workflow-detail-title">
          <div>
            <h1>{workflow.name}</h1>
            <span className={`badge ${mode.badge}`}>{mode.label}</span>
            {official && (
              <span className="badge badge-ash">
                <Lock size={9} />
                官方只读
              </span>
            )}
          </div>
          <p>{workflowDescription(workflow)}</p>
        </div>
        <dl className="workflow-detail-meta">
          <div>
            <dt>阶段</dt>
            <dd>{workflow.nodes.length}</dd>
          </div>
          <div>
            <dt>模型</dt>
            <dd>{models.length}</dd>
          </div>
          <div>
            <dt>版本</dt>
            <dd title={workflow.version}>{workflow.version}</dd>
          </div>
        </dl>
      </header>

      {error && (
        <div className="workflow-detail-error banner-warning" role="alert">
          {error}
        </div>
      )}

      <div className="workflow-detail-layout">
        <WorkflowStageDeck
          activeStageId={activeStage.id}
          qualityMode={workflow.quality_mode}
          workflow={workflow}
          onSelect={setActiveStageId}
        />

        <StageConfigurationPanel
          activeIndex={activeIndex}
          official={official}
          stage={activeStage}
          workflow={workflow}
          onChangeMode={(qualityMode) =>
            updateWorkflow({ ...workflow, quality_mode: qualityMode })
          }
          onChangeStage={updateStage}
          onCopy={() => void handleCopy()}
          onSave={() => void handleSave()}
          onUse={() => onUse(workflow.id)}
          actionState={actionState}
        />
      </div>
    </div>
  )
}

function StageConfigurationPanel({
  actionState,
  activeIndex,
  official,
  stage,
  workflow,
  onChangeMode,
  onChangeStage,
  onCopy,
  onSave,
  onUse,
}: {
  actionState: "idle" | "saving" | "saved" | "copying"
  activeIndex: number
  official: boolean
  stage: WorkflowStage
  workflow: WorkflowDefinition
  onChangeMode: (mode: QualityMode) => void
  onChangeStage: (stage: WorkflowStage) => void
  onCopy: () => void
  onSave: () => void
  onUse: () => void
}) {
  const providers = workflow.provider_profiles.filter(
    (profile) => profile.enabled,
  )
  const textProviders = providers.filter(
    (profile) => profile.kind === "openai-compatible",
  )
  const imageProviders = providers.filter(
    (profile) => profile.kind === "openai-compatible-image",
  )
  const provider = textProviders.find(
    (profile) => profile.id === stage.provider_profile_id,
  )
  const modelOptions = [
    ...new Set(
      [
        ...(provider?.model_options ?? []),
        provider?.default_model,
        stage.model_settings.model,
      ].filter(Boolean),
    ),
  ]

  const updateSettings = (patch: Partial<WorkflowStage["model_settings"]>) => {
    const modelSettings = { ...stage.model_settings, ...patch }
    onChangeStage({
      ...stage,
      model_settings: modelSettings,
      generation_budget: stage.generation_budget
        ? { ...stage.generation_budget, max_tokens: modelSettings.max_tokens }
        : stage.generation_budget,
    })
  }

  return (
    <aside
      className="workflow-config-panel"
      aria-label={`${stageShortLabel(stage)}阶段配置`}
    >
      <div className="workflow-config-scroll" key={stage.id}>
        <header className="workflow-config-head animate-fade-in">
          <div>
            <span>阶段 {String(activeIndex + 1).padStart(2, "0")}</span>
            <h2>{stageShortLabel(stage)}</h2>
          </div>
          <span className="workflow-config-provider">
            <Bot size={11} />
            {workflowProviderName(workflow, stage)}
          </span>
        </header>

        <p className="workflow-config-description animate-fade-in">
          {STAGE_DESCRIPTIONS[stage.id] ?? stage.label}
        </p>

        <section className="workflow-config-section animate-fade-in">
          <div className="workflow-config-section-title">
            <Settings2 size={12} />
            <span>执行配置</span>
          </div>
          {stage.type === "export" ? (
            <p className="workflow-config-system">
              该阶段由系统确定性执行，不调用 Provider。
            </p>
          ) : (
            <div className="workflow-config-fields">
              <label>
                <span>Provider</span>
                <select
                  className="input"
                  value={stage.provider_profile_id}
                  disabled={official}
                  onChange={(event) => {
                    const nextProvider = textProviders.find(
                      (item) => item.id === event.target.value,
                    )
                    onChangeStage({
                      ...stage,
                      provider_profile_id: event.target.value,
                      model_settings: {
                        ...stage.model_settings,
                        model:
                          nextProvider?.default_model ??
                          stage.model_settings.model,
                      },
                    })
                  }}
                >
                  {textProviders.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>模型</span>
                <select
                  className="input font-mono"
                  value={stage.model_settings.model}
                  disabled={official}
                  onChange={(event) =>
                    updateSettings({ model: event.target.value })
                  }
                >
                  {modelOptions.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
              {stage.type === "cover" && stage.image_provider_profile_id && (
                <label className="workflow-config-wide">
                  <span>图片 Provider</span>
                  <select
                    className="input"
                    value={stage.image_provider_profile_id}
                    disabled={official}
                    onChange={(event) =>
                      onChangeStage({
                        ...stage,
                        image_provider_profile_id: event.target.value,
                      })
                    }
                  >
                    {imageProviders.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.default_model}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                <span>生成预算</span>
                <input
                  className="input font-mono"
                  type="number"
                  min={256}
                  step={128}
                  value={stage.model_settings.max_tokens}
                  disabled={official}
                  onChange={(event) =>
                    updateSettings({ max_tokens: Number(event.target.value) })
                  }
                />
              </label>
              <label>
                <span>超时秒数</span>
                <input
                  className="input font-mono"
                  type="number"
                  min={10}
                  step={10}
                  value={stage.model_settings.timeout_seconds}
                  disabled={official}
                  onChange={(event) =>
                    updateSettings({
                      timeout_seconds: Number(event.target.value),
                    })
                  }
                />
              </label>
              <label className="workflow-config-wide">
                <span>
                  温度 · {stage.model_settings.temperature.toFixed(2)}
                </span>
                <input
                  type="range"
                  min={0}
                  max={1.5}
                  step={0.05}
                  value={stage.model_settings.temperature}
                  disabled={official}
                  onChange={(event) =>
                    updateSettings({ temperature: Number(event.target.value) })
                  }
                />
              </label>
            </div>
          )}
        </section>

        <section className="workflow-config-section animate-fade-in">
          <div className="workflow-config-section-title">
            <span>阶段合同</span>
          </div>
          <dl className="workflow-config-contract">
            <div>
              <dt>Prompt 绑定</dt>
              <dd className="font-mono">{stage.prompt_template_id || "无"}</dd>
            </div>
            <div>
              <dt>输入字段</dt>
              <dd>
                {stage.input_schema.length} 项 ·{" "}
                {stage.input_schema.filter((field) => field.required).length}{" "}
                项必填
              </dd>
            </div>
            <div>
              <dt>Artifact 架构</dt>
              <dd>Phase 27</dd>
            </div>
          </dl>
        </section>

        <section className="workflow-config-section animate-fade-in">
          <div className="workflow-config-section-title">
            <span>品质模式</span>
            <small>建书后冻结</small>
          </div>
          <div
            className="workflow-mode-control"
            role="radiogroup"
            aria-label="品质模式"
          >
            {(Object.keys(qualityModeMeta) as QualityMode[]).map(
              (qualityMode) => (
                <button
                  type="button"
                  role="radio"
                  aria-checked={workflow.quality_mode === qualityMode}
                  key={qualityMode}
                  disabled={official}
                  onClick={() => onChangeMode(qualityMode)}
                >
                  {qualityModeMeta[qualityMode].label}
                </button>
              ),
            )}
          </div>
          <p className="workflow-config-note">
            创建作品后锁定，运行过程中不可切换。
          </p>
        </section>
      </div>

      <footer className="workflow-config-actions">
        {official ? (
          <button
            type="button"
            onClick={onCopy}
            disabled={actionState === "copying"}
            className="btn btn-secondary"
          >
            <Copy size={12} />
            {actionState === "copying" ? "正在复制…" : "复制后配置"}
          </button>
        ) : (
          <button
            type="button"
            onClick={onSave}
            disabled={actionState === "saving"}
            className={`btn btn-secondary ${
              actionState === "saved" ? "text-mint" : ""
            }`}
          >
            {actionState === "saved" ? <Check size={12} /> : <Save size={12} />}
            {actionState === "saving"
              ? "正在保存…"
              : actionState === "saved"
                ? "已保存"
                : "保存配置"}
          </button>
        )}
        <button type="button" onClick={onUse} className="btn btn-primary">
          使用此流程 <ArrowRight size={12} />
        </button>
      </footer>
    </aside>
  )
}
