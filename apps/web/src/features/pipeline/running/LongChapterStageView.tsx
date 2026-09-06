import { useEffect, useMemo, useRef, useState } from "react"
import "../../../styles/phase32-long-chapter.css"
import {
  AlertTriangle,
  BookOpenText,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Lock,
  Play,
  Sparkles,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import {
  longChapterContractError,
  parsePhase32LongChapter,
} from "../lib/phase32LongChapter"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePhase32LongChapterContext } from "../state/usePhase32LongChapterContext"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import { LongChapterWorkbench } from "./LongChapterWorkbench"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { WritebackRecoveryNotice } from "./WritebackRecoveryNotice"

type ActionState = "idle" | "accepting" | "regenerating" | "retrying-writeback" | "cancelling"

export default function LongChapterStageView() {
  const {
    activeProject,
    activeRun,
    reconnectRun,
    refreshRun,
    runError,
    runLoading,
    setRoute,
  } = useApp()
  const [selectedChapterRef, setSelectedChapterRef] = useState("")
  const [dialog, setDialog] = useState<Phase32DecisionDialogKind | null>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] = useState<ActionState>("idle")
  const [actionError, setActionError] = useState("")
  const previousActiveChapterRef = useRef("")
  const runId = activeRun?.definition.run_id ?? ""
  const progress = activeRun?.read_model.sequential_stage_progress.text
  const orderedChapterRefs = progress?.ordered_unit_refs ?? []
  const committedArtifactRefs = progress?.committed_artifact_refs ?? {}
  const decision = activeRun?.read_model.pending_decisions.find(
    (item) => item.stage_id === "text",
  )
  const activeChapterRef =
    decision?.unit_ref || activeRun?.read_model.active_unit_ref || ""
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const artifactAvailable = Boolean(
    selectedChapterRef &&
      (committedArtifactRefs[selectedChapterRef] ||
        decision?.unit_ref === selectedChapterRef),
  )
  const draft = usePhase32ArtifactDraft(
    runId,
    "text",
    authorityRevision,
    artifactAvailable,
    selectedChapterRef,
  )
  const context = usePhase32LongChapterContext(
    runId,
    authorityRevision,
    Boolean(runId && orderedChapterRefs.length),
  )
  const parsed = useMemo(
    () => parsePhase32LongChapter(draft.payload),
    [draft.payload],
  )
  const editMode = useArtifactEditMode(
    draft.current?.editable ?? false,
    draft.current?.artifact_ref ?? "",
  )
  const contractError = parsed.error
    ? parsed.error
    : longChapterContractError(
        parsed.artifact,
        context.context,
        selectedChapterRef,
      )
  const loading = useLoadingPresence(
    runLoading || context.loading || (artifactAvailable && draft.loading),
  )

  useEffect(() => {
    const activeChapterChanged =
      Boolean(activeChapterRef) &&
      previousActiveChapterRef.current !== activeChapterRef
    previousActiveChapterRef.current = activeChapterRef
    if (activeChapterChanged) {
      setSelectedChapterRef(activeChapterRef)
      return
    }
    if (!selectedChapterRef || !orderedChapterRefs.includes(selectedChapterRef))
      setSelectedChapterRef(activeChapterRef || orderedChapterRefs[0] || "")
  }, [activeChapterRef, orderedChapterRefs, selectedChapterRef])

  if (!activeProject) return null
  if (loading.visible) {
    return (
      <BookLoader
        detail="读取卷章顺序、已接受版本、当前细纲与有限连续性交接"
        label="正在同步逐章正文工作台"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <LongChapterEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const status = activeRun.read_model.stage_status.text ?? "locked"
  const currentDecision = draft.current?.pending_decision ?? null
  const writebackRecovery = currentDecision?.kind === "writeback_recovery"
  const canDecide = Boolean(
    selectedChapterRef === activeChapterRef &&
      draft.current?.editable &&
      currentDecision?.domain_revision !== null,
  )
  const canRecoverWriteback = Boolean(
    selectedChapterRef === activeChapterRef &&
      writebackRecovery &&
      draft.current?.status === "committed" &&
      !draft.current.editable &&
      currentDecision?.domain_revision !== null,
  )
  const busy = actionState !== "idle"
  const activeTarget = activeRun.read_model.stage_manifest.find(
    (item) => item.stage_id === activeRun.read_model.active_stage_id,
  )

  const submitDecision = async (
    action: "accept" | "regenerate" | "retry_writeback" | "cancel",
  ) => {
    if (!currentDecision || currentDecision.domain_revision === null || busy)
      return
    if (action === "accept" && contractError) {
      setActionError(contractError)
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写当前章节的定向换稿要求")
      return
    }
    setActionState(
      action === "accept"
        ? "accepting"
        : action === "regenerate"
          ? "regenerating"
          : action === "retry_writeback"
            ? "retrying-writeback"
            : "cancelling",
    )
    setActionError("")
    try {
      const draftRef = action === "accept" ? await draft.flush() : ""
      const resolved = await resolvePhase32RunDecision(runId, {
        decisionId: currentDecision.decision_id,
        action,
        domainRevision: currentDecision.domain_revision,
        direction: action === "regenerate" ? direction : undefined,
        draftRef: draftRef || undefined,
      })
      setDialog(null)
      setDirection("")
      await refreshRun()
      reconnectRun()
      if (action === "accept" || action === "retry_writeback") {
        const nextStageId = resolved.read_model.active_stage_id
        if (nextStageId !== "text" && isProductionStageRoute(nextStageId))
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "章节正文决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (!orderedChapterRefs.length) {
    return status === "running" ? (
      <BookLoader
        detail="系统会从已确认 Rolling Detail 冻结章节顺序后逐章生成"
        label="正在准备长篇章节"
        variant="compact"
      />
    ) : (
      <LongChapterEmptyState
        actionLabel="前往运行监控"
        detail={runError || "请先完成并确认当前长篇滚动细纲。"}
        onAction={() => setRoute("run-monitor")}
        title="逐章正文尚未开始"
      />
    )
  }

  const selectedAccepted = Boolean(committedArtifactRefs[selectedChapterRef])
  const chapterNumber = String(
    orderedChapterRefs.indexOf(selectedChapterRef) + 1,
  ).padStart(2, "0")
  const selectedSafe = selectedAccepted || writebackRecovery
  const revisionLabel = writebackRecovery
    ? `CH${chapterNumber} · 已接受不可变版本 · 正式写回待恢复`
    : currentDecision
      ? `CH${chapterNumber} · Revision ${currentDecision.domain_revision ?? "历史"} · 换稿 ${currentDecision.redraft_used ?? "-"}/${currentDecision.redraft_limit ?? "-"}`
      : selectedAccepted
        ? "已接受不可变版本"
        : "等待前序章节"

  return (
    <div className="long-chapter-page page-in">
      <header className="long-chapter-toolbar">
        <div className="long-chapter-toolbar-state">
          {selectedSafe ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {writebackRecovery
              ? "当前章节已接受 · 正式写回待恢复"
              : selectedAccepted
                ? "当前章节已接受"
                : canDecide
                  ? "当前章节等待作者决策"
                  : "章节尚未进入生成"}
          </span>
          <small>{draftStatusLabel(draft.status, artifactAvailable)}</small>
        </div>
        <div className="long-chapter-actions">
          <ArtifactModeSwitch
            canEdit={draft.current?.editable ?? false}
            editing={editMode.editing}
            onEdit={editMode.edit}
            onShow={editMode.show}
          />
          {canDecide &&
          currentDecision?.allowed_actions.includes("regenerate") ? (
            <button
              className="btn btn-secondary text-xs"
              disabled={busy}
              onClick={() => setDialog("regenerate")}
              type="button"
            >
              <Sparkles size={12} /> 定向换稿
            </button>
          ) : null}
          {canDecide && currentDecision?.allowed_actions.includes("cancel") ? (
            <button
              className="btn btn-ghost text-risk text-xs"
              disabled={busy}
              onClick={() => setDialog("cancel")}
              type="button"
            >
              <CircleStop size={12} /> 取消
            </button>
          ) : null}
          {canDecide && currentDecision?.allowed_actions.includes("accept") ? (
            <button
              className="btn btn-primary text-xs"
              disabled={
                busy || draft.status === "error" || Boolean(contractError)
              }
              onClick={() => void submitDecision("accept")}
              type="button"
            >
              <Lock size={12} />
              {actionState === "accepting"
                ? "正在确认…"
                : `确认 CH${chapterNumber}`}
            </button>
          ) : activeTarget?.stage_id === "cover" && selectedAccepted ? (
            <button
              className="btn btn-primary text-xs"
              onClick={() => setRoute("cover")}
              type="button"
            >
              进入封面阶段 <Play size={12} />
            </button>
          ) : null}
        </div>
      </header>

      {(actionError || draft.error || context.error || runError) && (
        <div className="long-chapter-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{actionError || draft.error || context.error || runError}</span>
        </div>
      )}

      {canRecoverWriteback ? (
        <WritebackRecoveryNotice
          busy={busy}
          onCancel={() => setDialog("cancel")}
          onRetry={() => void submitDecision("retry_writeback")}
          unitLabel={`CH${chapterNumber}`}
        />
      ) : null}

      <LongChapterWorkbench
        activeChapterRef={activeChapterRef}
        artifact={artifactAvailable ? parsed.artifact : null}
        artifactRef={draft.current?.artifact_ref ?? ""}
        committedArtifactRefs={committedArtifactRefs}
        editable={editMode.editing}
        onChange={draft.change}
        onSelectChapter={setSelectedChapterRef}
        orderedChapterRefs={orderedChapterRefs}
        referenceContext={context.context}
        revisionLabel={revisionLabel}
        selectedChapterRef={selectedChapterRef || orderedChapterRefs[0]}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          busy={busy}
          direction={direction}
          error={actionError}
          id="phase32-long-chapter-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留本章的取证结果和下一章交接，压缩解释性复述，让冲突通过动作升级；不改变章节标题、POV 与冻结细纲。"
          regenerateDescription="只重写当前章节；卷册身份、标题、POV、章节顺序和全部已接受前缀保持冻结。"
          suggestions={[
            "保留本章戏剧任务与退出状态，减少概述式说明和重复心理活动。",
            "让当前场景目标与对抗逐级升级，不提前消费下一章的揭示。",
            "维持当前 POV 的观察边界、人物声音与上一章交接结果。",
          ]}
        />
      ) : null}
    </div>
  )
}

function LongChapterEmptyState({
  actionLabel,
  detail,
  onAction,
  title,
}: {
  actionLabel: string
  detail: string
  onAction: () => void
  title: string
}) {
  return (
    <div className="long-chapter-empty page-in">
      <BookOpenText size={22} />
      <h1>{title}</h1>
      <p>{detail}</p>
      <button
        className="btn btn-secondary text-xs"
        onClick={onAction}
        type="button"
      >
        {actionLabel} <Play size={12} />
      </button>
    </div>
  )
}

function draftStatusLabel(status: string, available: boolean) {
  if (!available) return "等待前序"
  return (
    ({
      clean: "原始候选",
      dirty: "等待自动保存",
      saving: "正在保存",
      saved: "草稿已保存",
      readonly: "权威版本",
      error: "草稿异常",
    } as Record<string, string>)[status] ?? ""
  )
}
