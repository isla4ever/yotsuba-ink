import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  GitBranch,
  Layers3,
  Lock,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import {
  parseStorySpineArtifact,
  type StoryMilestone,
  type StoryProgressType,
  type StorySpineArtifact,
  type StorySpineTurn,
} from "@/features/pipeline/contracts/artifacts"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import { resolveRunDecision } from "@/features/pipeline/services/runApi"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"

type DialogKind = "regenerate" | "cancel" | null

const PROGRESS_META: Record<StoryProgressType, {
  label: string
  className: string
}> = {
  information: { label: "信息推进", className: "spine-progress-information" },
  relationship: { label: "关系推进", className: "spine-progress-relationship" },
  external: { label: "外部推进", className: "spine-progress-external" },
  internal: { label: "内在推进", className: "spine-progress-internal" },
}

const MILESTONE_LABEL: Record<StoryMilestone, string> = {
  inciting: "启动事件",
  commitment: "行动承诺",
  midpoint_reversal: "中心反转",
  crisis: "危机",
  climax: "高潮",
  aftermath: "余波",
}

export default function SpineStageView() {
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
    spineSelectedId,
    setSpineSelectedId,
  } = useApp()
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "spine"),
    [activeRun],
  )
  const committed = runArtifacts.spine
  const candidate = runCandidateArtifacts.spine
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const draft = useStageArtifactDraft(runId, decision, source)
  const parsed = useMemo(
    () => parseStorySpineArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] =
    useState<"idle" | "accepting" | "regenerating" | "cancelling">("idle")
  const [actionError, setActionError] = useState("")
  const artifact = parsed.artifact
  const turnSignature = artifact?.turns.map((turn) => turn.id).join("|") ?? ""

  useEffect(() => {
    if (!artifact?.turns.length) return
    if (!artifact.turns.some((turn) => turn.id === spineSelectedId))
      setSpineSelectedId(artifact.turns[0].id)
  }, [artifact, setSpineSelectedId, spineSelectedId, turnSignature])

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!activeRun || !decision || actionState !== "idle") return
    if (action === "accept" && !artifact) {
      setActionError(parsed.error || "当前稿未通过 Story Spine 合同校验")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次因果重规划方向")
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
          ? artifact as unknown as Record<string, unknown>
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

  const stageStatus = activeRun?.read_model.stage_status.spine ?? "locked"
  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)
  const generationLoad = useLoadingPresence(
    (!source || !artifact) && stageStatus === "running",
  )

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在同步故事脊柱"
        detail="读取因果链候选稿与正式 Artifact"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <SpineEmpty
        title="当前作品尚未启动创作 Run"
        detail="Run 启动后，故事脊柱会在这里进入作者定稿。"
        onBack={() => setRoute("studio")}
      />
    )
  }

  if (generationLoad.visible || !source || !artifact) {
    return (
      <div className="flex-1 flex flex-col page-in">
        <SpineStageBar
          status={stageStatus}
          detail={
            stageStatus === "running"
              ? "Provider 正在生成因果链"
              : "当前阶段尚无可展示产物"
          }
        />
        <div className="flex-1 grid place-items-center p-6">
          {generationLoad.visible ? (
            <BookLoader
              phase={generationLoad.exiting ? "exit" : "enter"}
              variant="compact"
              label="正在生成 Story Spine"
              detail="因果链通过容量与结构合同后会进入候选稿"
            />
          ) : (
            <div className="max-w-lg text-center">
              <Lock size={22} className="text-fog mx-auto mb-3" />
              <h1 className="text-sm font-semibold text-ink mb-1">
                Story Spine 尚未就绪
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

  const selectedIndex = Math.max(
    0,
    artifact.turns.findIndex((turn) => turn.id === spineSelectedId),
  )
  const selectedTurn = artifact.turns[selectedIndex]
  const editable = Boolean(decision && candidate)
  const committedAt = committed?.created_at
    ? formatTime(committed.created_at)
    : ""

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <SpineStageBar
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
              {actionState === "accepting" ? "正在定稿…" : "确认因果链"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-primary text-xs"
            onClick={() => setRoute("cast")}
          >
            查看人物编排 <ArrowRight size={12} />
          </button>
        )}
      </SpineStageBar>

      {(actionError || draft.error || runArtifactError) && (
        <div className="mx-4 md:mx-5 mt-3 banner-warning" role="alert">
          {actionError || draft.error || runArtifactError}
        </div>
      )}

      <div className="spine-workbench">
        <SpineChainSidebar
          turns={artifact.turns}
          selectedId={selectedTurn.id}
          onSelect={setSpineSelectedId}
        />

        <main className="spine-workspace-scroll">
          <MobileTurnPicker
            turns={artifact.turns}
            selectedId={selectedTurn.id}
            onSelect={setSpineSelectedId}
          />
          <TurnWorkspace
            artifact={artifact}
            editable={editable}
            index={selectedIndex}
            turn={selectedTurn}
            onArtifactChange={draft.change}
          />
        </main>
      </div>

      {dialog === "regenerate" && (
        <DecisionDialog
          title="定向重规划因果链"
          onClose={() => setDialog(null)}
        >
          <p>运行时会保留冻结篇幅和 Turn 数量，只按你的方向重做宏观因果链。</p>
          <label>
            <span>修订方向</span>
            <textarea
              className="input"
              rows={4}
              value={direction}
              onChange={(event) => setDirection(event.target.value)}
              placeholder="例如：让中心反转更早回收启动事件，并强化终局代价。"
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

function SpineChainSidebar({
  turns,
  selectedId,
  onSelect,
}: {
  turns: StorySpineTurn[]
  selectedId: string
  onSelect: (id: string) => void
}) {
  return (
    <aside className="spine-secondary-sidebar" aria-label="因果链导航">
      <header>
        <span>因果链</span>
        <strong>{turns.length} Turns</strong>
      </header>
      <nav>
        <div className="spine-chain-rail" aria-hidden="true" />
        {turns.map((turn, index) => {
          const active = turn.id === selectedId
          const milestone = turn.milestones[0]
          return (
            <button
              key={turn.id}
              type="button"
              className={active ? "active" : ""}
              onClick={() => onSelect(turn.id)}
            >
              <span
                className={`spine-chain-dot ${PROGRESS_META[turn.progress_type].className}`}
              />
              <span className="spine-chain-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="spine-chain-copy">
                <strong>
                  {milestone
                    ? MILESTONE_LABEL[milestone]
                    : PROGRESS_META[turn.progress_type].label}
                </strong>
                <small>{turn.change}</small>
              </span>
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

function MobileTurnPicker({
  turns,
  selectedId,
  onSelect,
}: {
  turns: StorySpineTurn[]
  selectedId: string
  onSelect: (id: string) => void
}) {
  return (
    <div className="spine-mobile-picker" aria-label="选择因果转折">
      {turns.map((turn, index) => (
        <button
          key={turn.id}
          type="button"
          className={turn.id === selectedId ? "active" : ""}
          onClick={() => onSelect(turn.id)}
        >
          <span
            className={`spine-chain-dot ${PROGRESS_META[turn.progress_type].className}`}
          />
          {String(index + 1).padStart(2, "0")}
        </button>
      ))}
    </div>
  )
}

function TurnWorkspace({
  artifact,
  editable,
  index,
  turn,
  onArtifactChange,
}: {
  artifact: StorySpineArtifact
  editable: boolean
  index: number
  turn: StorySpineTurn
  onArtifactChange: (artifact: Record<string, unknown>) => void
}) {
  const previous = artifact.turns[index - 1]
  const next = artifact.turns[index + 1]
  const progress = PROGRESS_META[turn.progress_type]
  return (
    <div className="spine-turn-workspace animate-fade-in" key={turn.id}>
      <header className="spine-turn-heading">
        <div>
          <span className="spine-turn-kicker">
            {turn.id.toUpperCase()} · {index + 1} / {artifact.turns.length}
          </span>
          <h1>
            {turn.milestones.length
              ? turn.milestones.map((item) => MILESTONE_LABEL[item]).join(" / ")
              : progress.label}
          </h1>
        </div>
        {editable ? (
          <label className="spine-progress-select">
            <span>推进类型</span>
            <select
              className="input"
              value={turn.progress_type}
              onChange={(event) =>
                updateTurn(onArtifactChange, artifact, turn.id, {
                  progress_type: event.target.value as StoryProgressType,
                })
              }
            >
              {Object.entries(PROGRESS_META).map(([value, meta]) => (
                <option key={value} value={value}>
                  {meta.label}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className={`spine-progress-badge ${progress.className}`}>
            {progress.label}
          </span>
        )}
      </header>

      <div className="spine-turn-grid">
        <section className="spine-causal-editor">
          <label className="spine-artifact-field">
            <span>前因 · CAUSE</span>
            <textarea
              className="input font-serif"
              data-collaboration-field-path={`turns.${index}.cause`}
              data-collaboration-unit={turn.id}
              rows={3}
              value={turn.cause}
              readOnly={!editable}
              onChange={(event) =>
                updateTurn(onArtifactChange, artifact, turn.id, {
                  cause: event.target.value,
                })
              }
            />
          </label>
          <div className="spine-causal-connector">
            <ArrowDown size={14} />
            <span>因此发生不可逆变化</span>
          </div>
          <label className="spine-artifact-field spine-change-field">
            <span>变化 · CHANGE</span>
            <textarea
              className="input font-serif"
              data-collaboration-field-path={`turns.${index}.change`}
              data-collaboration-unit={turn.id}
              rows={3}
              value={turn.change}
              readOnly={!editable}
              onChange={(event) =>
                updateTurn(onArtifactChange, artifact, turn.id, {
                  change: event.target.value,
                })
              }
            />
          </label>
        </section>

        <aside className="spine-context-column">
          <section>
            <div className="spine-context-title">
              <GitBranch size={12} />
              <span>因果交接</span>
            </div>
            <dl>
              <div>
                <dt>前置变化</dt>
                <dd>{previous?.change ?? "由 Story Brief 的故事承诺启动"}</dd>
              </div>
              <div>
                <dt>下一前因</dt>
                <dd>{next?.cause ?? "进入全书结局与余波"}</dd>
              </div>
            </dl>
          </section>
          <section>
            <div className="spine-context-title">
              <Layers3 size={12} />
              <span>结构锚点</span>
            </div>
            {turn.milestones.length ? (
              <div className="spine-milestone-list">
                {turn.milestones.map((milestone) => (
                  <span key={milestone}>{MILESTONE_LABEL[milestone]}</span>
                ))}
              </div>
            ) : (
              <p>此 Turn 承担{progress.label}，不占用六个代码冻结里程碑。</p>
            )}
          </section>
        </aside>
      </div>

      <section className="spine-ending-section">
        <div className="spine-section-heading">
          <span>结局兑现</span>
          <strong>整条因果链的唯一终局</strong>
        </div>
        <textarea
          className="input font-serif"
          data-collaboration-field-path="ending"
          data-collaboration-unit="artifact"
          rows={5}
          value={artifact.ending}
          readOnly={!editable}
          onChange={(event) =>
            updateArtifact(onArtifactChange, artifact, {
              ending: event.target.value,
            })
          }
        />
      </section>

      <section className="spine-ending-section">
        <div className="spine-section-heading">
          <span>保留问题</span>
          <strong>{artifact.open_questions.length} 项</strong>
        </div>
        <div className="spine-open-question-list">
          {artifact.open_questions.map((question, questionIndex) => (
            <div key={questionIndex}>
              <span>{String(questionIndex + 1).padStart(2, "0")}</span>
              <textarea
                className="input"
                data-collaboration-field-path={`open_questions.${questionIndex}`}
                data-collaboration-unit="artifact"
                rows={2}
                value={question}
                readOnly={!editable}
                onChange={(event) =>
                  updateArtifact(onArtifactChange, artifact, {
                    open_questions: artifact.open_questions.map((item, index) =>
                      index === questionIndex ? event.target.value : item,
                    ),
                  })
                }
              />
              {editable && artifact.open_questions.length > 1 && (
                <button
                  type="button"
                  aria-label={`删除保留问题 ${questionIndex + 1}`}
                  title="删除此问题"
                  onClick={() =>
                    updateArtifact(onArtifactChange, artifact, {
                      open_questions: artifact.open_questions.filter(
                        (_, index) => index !== questionIndex,
                      ),
                    })
                  }
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
          {editable && (
            <button
              type="button"
              className="spine-add-question"
              onClick={() =>
                updateArtifact(onArtifactChange, artifact, {
                  open_questions: [...artifact.open_questions, "待回答的问题"],
                })
              }
            >
              <Plus size={12} />
              添加保留问题
            </button>
          )}
        </div>
      </section>
    </div>
  )
}

function SpineStageBar({
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
    <div className="stage-aura border-b border-hairline bg-surface px-4 md:px-5 py-3 flex items-center gap-3 shrink-0">
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
            ? "脊柱已定稿"
            : status === "running"
              ? "脊柱生成中"
              : "脊柱等待决策"}
        </span>
        <span className="hidden md:inline text-[10px] font-mono text-fog truncate">
          · {detail}
        </span>
      </div>
      {children}
    </div>
  )
}

function SpineEmpty({
  title,
  detail,
  onBack,
}: {
  title: string
  detail: string
  onBack: () => void
}) {
  return (
    <div className="flex-1 grid place-items-center p-6 page-in">
      <div className="max-w-md text-center">
        <FilePenLine size={22} className="text-fog mx-auto mb-3" />
        <h1 className="text-sm font-semibold text-ink mb-1">{title}</h1>
        <p className="text-xs text-fog mb-4">{detail}</p>
        <button
          type="button"
          className="btn btn-secondary text-xs"
          onClick={onBack}
        >
          返回作品库
        </button>
      </div>
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
        aria-labelledby="spine-dialog-title"
      >
        <h2
          id="spine-dialog-title"
          className="text-sm font-semibold text-ink mb-2"
        >
          {title}
        </h2>
        <div className="text-xs text-fog leading-relaxed">{children}</div>
      </section>
    </div>
  )
}

function updateTurn(
  change: (artifact: Record<string, unknown>) => void,
  artifact: StorySpineArtifact,
  turnId: string,
  patch: Partial<StorySpineTurn>,
) {
  const turns = artifact.turns.map((turn) =>
    turn.id === turnId ? { ...turn, ...patch } : turn,
  )
  change({
    ...artifact,
    turns,
    progress_types: Array.from(
      new Set(turns.map((turn) => turn.progress_type)),
    ),
  } as unknown as Record<string, unknown>)
}

function updateArtifact(
  change: (artifact: Record<string, unknown>) => void,
  artifact: StorySpineArtifact,
  patch: Partial<StorySpineArtifact>,
) {
  change({ ...artifact, ...patch } as unknown as Record<string, unknown>)
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
