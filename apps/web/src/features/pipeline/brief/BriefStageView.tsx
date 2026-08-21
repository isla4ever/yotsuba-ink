import { useMemo, useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Lock,
  RefreshCw,
  Save,
  Sparkles,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import {
  parseStoryBriefArtifact,
  type StoryBriefArtifact,
} from "@/features/pipeline/contracts/artifacts"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import { resolveRunDecision } from "@/features/pipeline/services/runApi"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"

type DialogKind = "regenerate" | "cancel" | null

export default function BriefStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runCandidateArtifacts,
    runLoading,
    setRoute,
  } = useApp()
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "brief"),
    [activeRun],
  )
  const committed = runArtifacts.brief
  const candidate = runCandidateArtifacts.brief
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const draft = useStageArtifactDraft(runId, decision, source)
  const parsed = useMemo(
    () => parseStoryBriefArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] =
    useState<"idle" | "accepting" | "regenerating" | "cancelling">("idle")
  const [actionError, setActionError] = useState("")
  const stageStatus = activeRun?.read_model.stage_status.brief ?? "locked"
  const editable = Boolean(decision && candidate && parsed.artifact)

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!activeRun || !decision || actionState !== "idle") return
    if (action === "accept" && !parsed.artifact) {
      setActionError(parsed.error || "当前稿未通过 Story Brief 合同校验")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次换稿方向")
      return
    }
    setActionState(
      action === "accept"
        ? "accepting"
        : action === "regenerate"
          ? "regenerating"
          : "cancelling",
    )
    setActionError("")
    try {
      await resolveRunDecision(
        activeRun.definition.run_id,
        decision.decisionId,
        action,
        decision.domainRevision,
        action === "accept"
          ? parsed.artifact as unknown as Record<string, unknown>
          : undefined,
        action === "regenerate" ? direction : undefined,
      )
      setDialog(null)
      setDirection("")
      await refreshRun()
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "阶段决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)
  const generationLoad = useLoadingPresence(
    (!source || !parsed.artifact) && stageStatus === "running",
  )

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在同步创作立项"
        detail="读取 Story Brief 候选稿与正式 Artifact"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <div className="flex-1 grid place-items-center p-6 page-in">
        <div className="max-w-md text-center">
          <FilePenLine size={22} className="text-fog mx-auto mb-3" />
          <h1 className="text-sm font-semibold text-ink mb-1">
            当前作品尚未启动创作 Run
          </h1>
          <p className="text-xs text-fog mb-4">
            Run 启动后，模型生成的 Story Brief 会在这里进入作者定稿。
          </p>
          <button
            type="button"
            className="btn btn-secondary text-xs"
            onClick={() => setRoute("studio")}
          >
            返回作品库
          </button>
        </div>
      </div>
    )
  }

  if (generationLoad.visible || !source || !parsed.artifact) {
    return (
      <div className="flex-1 flex flex-col page-in">
        <StageBar
          status={stageStatus}
          detail={
            stageStatus === "running"
              ? "Provider 正在生成创作立项"
              : "当前阶段尚无可展示产物"
          }
        />
        <div className="flex-1 grid place-items-center p-6">
          {generationLoad.visible ? (
            <BookLoader
              phase={generationLoad.exiting ? "exit" : "enter"}
              variant="compact"
              label="正在生成 Story Brief"
              detail="模型输出通过合同校验后会进入候选稿"
            />
          ) : (
            <div className="max-w-lg text-center">
              <Lock size={22} className="text-fog mx-auto mb-3" />
              <h1 className="text-sm font-semibold text-ink mb-1">
                Story Brief 尚未就绪
              </h1>
              <p className="text-xs text-fog">
                {runArtifactError ||
                  parsed.error ||
                  "阶段解锁并产出候选稿后会自动显示。"}
              </p>
            </div>
          )}
        </div>
      </div>
    )
  }

  const artifact = parsed.artifact
  const committedAt = committed?.created_at
    ? formatTime(committed.created_at)
    : ""

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <StageBar
        status={decision ? "awaiting_decision" : "completed"}
        detail={
          decision
            ? `候选稿 ${candidate?.artifact_id ?? ""} · ${draftStatusLabel(draft.status)}`
            : `正式 Artifact ${committed?.artifact_id ?? ""}${
                committedAt ? ` · ${committedAt}` : ""
              }`
        }
      >
        {decision ? (
          <>
            {decision.allowedActions.includes("regenerate") && (
              <button
                type="button"
                className="btn btn-secondary text-xs"
                onClick={() => setDialog("regenerate")}
              >
                <Sparkles size={12} />
                定向换稿
              </button>
            )}
            {decision.allowedActions.includes("cancel") && (
              <button
                type="button"
                className="btn btn-ghost text-risk text-xs"
                onClick={() => setDialog("cancel")}
              >
                <CircleStop size={12} />
                取消运行
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary text-xs"
              disabled={!editable || actionState !== "idle"}
              onClick={() => void submitDecision("accept")}
            >
              <Lock size={12} />
              {actionState === "accepting" ? "正在定稿…" : "确认定稿"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-primary text-xs"
            onClick={() => setRoute("spine")}
          >
            查看故事脊柱 <ArrowRight size={12} />
          </button>
        )}
      </StageBar>

      {(actionError || draft.error || runArtifactError) && (
        <div className="mx-4 md:mx-6 mt-3 banner-warning" role="alert">
          {actionError || draft.error || runArtifactError}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <main className="brief-workbench">
          <header className="brief-workbench-head">
            <div>
              <span>
                {decision ? "候选稿 · 等待作者决策" : "正式 Artifact · 只读"}
              </span>
              <h1>创作立项</h1>
            </div>
            <div className="brief-contract-state">
              {decision ? (
                <FilePenLine size={13} />
              ) : (
                <CheckCircle2 size={13} />
              )}
              <span>
                {decision ? "编辑只影响当前候选稿" : "下游阶段均引用此版本"}
              </span>
            </div>
          </header>

          <section className="brief-section brief-core-section">
            <div className="brief-section-heading">
              <span>故事契约</span>
              <strong>全书唯一的承诺来源</strong>
            </div>
            <label className="brief-field brief-title-field">
              <span>正式书名</span>
              <input
                className="input font-serif"
                value={artifact.title}
                readOnly={!editable}
                onChange={(event) =>
                  updateArtifact(draft.change, artifact, {
                    title: event.target.value,
                  })
                }
              />
            </label>
            <label className="brief-field">
              <span>故事前提</span>
              <textarea
                className="input font-serif"
                rows={4}
                value={artifact.premise}
                readOnly={!editable}
                onChange={(event) =>
                  updateArtifact(draft.change, artifact, {
                    premise: event.target.value,
                  })
                }
              />
            </label>
            <div className="brief-field-grid">
              <label className="brief-field">
                <span>读者承诺</span>
                <textarea
                  className="input"
                  rows={4}
                  value={artifact.promise}
                  readOnly={!editable}
                  onChange={(event) =>
                    updateArtifact(draft.change, artifact, {
                      promise: event.target.value,
                    })
                  }
                />
              </label>
              <label className="brief-field">
                <span>主题问题</span>
                <textarea
                  className="input"
                  rows={4}
                  value={artifact.theme}
                  readOnly={!editable}
                  onChange={(event) =>
                    updateArtifact(draft.change, artifact, {
                      theme: event.target.value,
                    })
                  }
                />
              </label>
              <label className="brief-field">
                <span>结局承诺</span>
                <textarea
                  className="input"
                  rows={4}
                  value={artifact.ending_promise}
                  readOnly={!editable}
                  onChange={(event) =>
                    updateArtifact(draft.change, artifact, {
                      ending_promise: event.target.value,
                    })
                  }
                />
              </label>
            </div>
          </section>

          <section className="brief-section">
            <div className="brief-section-heading">
              <span>世界与声音</span>
              <strong>{artifact.world_rules.length} 条持续规则</strong>
            </div>
            <label className="brief-field">
              <span>最少必要世界规则</span>
              <textarea
                className="input"
                rows={Math.max(4, artifact.world_rules.length + 1)}
                value={artifact.world_rules.join("\n")}
                readOnly={!editable}
                onChange={(event) =>
                  updateArtifact(draft.change, artifact, {
                    world_rules: splitLines(event.target.value),
                  })
                }
              />
            </label>
            <label className="brief-field">
              <span>叙事声音</span>
              <textarea
                className="input"
                rows={4}
                value={artifact.voice}
                readOnly={!editable}
                onChange={(event) =>
                  updateArtifact(draft.change, artifact, {
                    voice: event.target.value,
                  })
                }
              />
            </label>
          </section>

          <section className="brief-section brief-length-section">
            <div className="brief-section-heading">
              <span>冻结篇幅</span>
              <strong>结构数量由代码计算</strong>
            </div>
            <div>
              <span>全书软目标</span>
              <strong>
                {artifact.length_envelope.word_target_soft.toLocaleString()} 字
              </strong>
              <small>
                如需改变篇幅，必须新建 Run；候选编辑不能修改冻结输入。
              </small>
            </div>
          </section>

          {!decision && (
            <div className="brief-commit-note">
              <Lock size={13} />
              <span>
                此 Story Brief 已正式写入
                ArtifactStore。当前页面不提供虚假的“解锁”；需要改写上游时应从稳定检查点创建新分支。
              </span>
            </div>
          )}
        </main>
      </div>

      {dialog === "regenerate" && (
        <DecisionDialog title="定向换一稿" onClose={() => setDialog(null)}>
          <p>
            只填写需要改变的方向；运行时会沿同一冻结篇幅与工作流重新生成 Brief。
          </p>
          <label>
            <span>修订方向</span>
            <textarea
              className="input"
              rows={4}
              value={direction}
              onChange={(event) => setDirection(event.target.value)}
              placeholder="例如：强化核心两难，让结局代价更不可逆。"
            />
          </label>
          <div className="flex gap-2 mt-4">
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setDialog(null)}
            >
              返回
            </button>
            <button
              type="button"
              className="btn btn-primary flex-1"
              disabled={!direction.trim() || actionState !== "idle"}
              onClick={() => void submitDecision("regenerate")}
            >
              <Sparkles size={12} />
              {actionState === "regenerating" ? "正在提交…" : "重新生成"}
            </button>
          </div>
        </DecisionDialog>
      )}

      {dialog === "cancel" && (
        <DecisionDialog title="取消当前 Run？" onClose={() => setDialog(null)}>
          <div className="banner-risk">
            <AlertTriangle size={13} />
            <span>
              取消后当前 Run 停止推进，已提交 Artifact 仍保留为历史证据。
            </span>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setDialog(null)}
            >
              返回
            </button>
            <button
              type="button"
              className="btn btn-danger flex-1"
              disabled={actionState !== "idle"}
              onClick={() => void submitDecision("cancel")}
            >
              <CircleStop size={12} />
              {actionState === "cancelling" ? "正在取消…" : "确认取消"}
            </button>
          </div>
        </DecisionDialog>
      )}
    </div>
  )
}

function StageBar({
  status,
  detail,
  children,
}: {
  status: string
  detail: string
  children?: React.ReactNode
}) {
  const completed = status === "completed"
  return (
    <div className="stage-aura border-b border-hairline bg-surface px-4 md:px-6 py-3 flex items-center gap-3 shrink-0">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {completed ? (
          <CheckCircle2 size={13} className="text-mint shrink-0" />
        ) : (
          <Save size={13} className="text-action shrink-0" />
        )}
        <span
          className={`text-xs font-medium ${
            completed ? "text-mint" : "text-action"
          }`}
        >
          {completed
            ? "简报已定稿"
            : status === "running"
              ? "简报生成中"
              : "简报等待决策"}
        </span>
        <span className="hidden md:inline text-[10px] font-mono text-fog truncate">
          · {detail}
        </span>
      </div>
      {children}
    </div>
  )
}

function DecisionDialog({
  title,
  children,
  onClose,
}: {
  title: string
  children: React.ReactNode
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/55 backdrop-blur-sm"
        onClick={onClose}
        aria-label="关闭对话框"
      />
      <section
        className="relative bg-elev border border-hairline rounded-lg w-full max-w-md p-5 animate-fade-in"
        role="dialog"
        aria-modal="true"
        aria-labelledby="brief-dialog-title"
      >
        <h2
          id="brief-dialog-title"
          className="text-sm font-semibold text-ink mb-2"
        >
          {title}
        </h2>
        <div className="text-xs text-fog leading-relaxed">{children}</div>
      </section>
    </div>
  )
}

function updateArtifact(
  change: (artifact: Record<string, unknown>) => void,
  artifact: StoryBriefArtifact,
  patch: Partial<StoryBriefArtifact>,
) {
  change({ ...artifact, ...patch } as unknown as Record<string, unknown>)
}

function splitLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false })
}

function draftStatusLabel(status: string) {
  return (
    ({
      loading: "正在读取草稿",
      clean: "尚未修改",
      dirty: "等待自动保存",
      saving: "正在保存",
      saved: "草稿已保存",
      error: "保存失败",
      idle: "候选稿",
    } as Record<string, string>)[status] ?? status
  )
}
