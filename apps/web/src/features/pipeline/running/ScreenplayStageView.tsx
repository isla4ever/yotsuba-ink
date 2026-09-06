import { useEffect, useMemo, useRef, useState } from "react"
import "../../../styles/phase32-screenplay.css"
import {
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Film,
  Lock,
  Play,
  Sparkles,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import {
  parsePhase32Screenplay,
  screenplayContractError,
} from "../lib/phase32Screenplay"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePhase32ScreenplayContext } from "../state/usePhase32ScreenplayContext"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { ScreenplayArtifactEditor } from "./ScreenplayArtifactEditor"
import { WritebackRecoveryNotice } from "./WritebackRecoveryNotice"

type ActionState = "idle" | "accepting" | "regenerating" | "retrying-writeback" | "cancelling"

export default function ScreenplayStageView() {
  const {
    activeProject,
    activeRun,
    reconnectRun,
    refreshRun,
    runError,
    runLoading,
    setRoute,
  } = useApp()
  const [selectedSceneRef, setSelectedSceneRef] = useState("")
  const [dialog, setDialog] = useState<Phase32DecisionDialogKind | null>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] = useState<ActionState>("idle")
  const [actionError, setActionError] = useState("")
  const previousActiveSceneRef = useRef("")
  const runId = activeRun?.definition.run_id ?? ""
  const progress = activeRun?.read_model.sequential_stage_progress.script
  const orderedSceneRefs = progress?.ordered_unit_refs ?? []
  const committedArtifactRefs = progress?.committed_artifact_refs ?? {}
  const decision = activeRun?.read_model.pending_decisions.find(
    (item) => item.stage_id === "script",
  )
  const activeSceneRef =
    decision?.unit_ref || activeRun?.read_model.active_unit_ref || ""
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const artifactAvailable = Boolean(
    selectedSceneRef &&
      (committedArtifactRefs[selectedSceneRef] ||
        decision?.unit_ref === selectedSceneRef),
  )
  const draft = usePhase32ArtifactDraft(
    runId,
    "script",
    authorityRevision,
    artifactAvailable,
    selectedSceneRef,
  )
  const context = usePhase32ScreenplayContext(
    runId,
    authorityRevision,
    Boolean(runId && orderedSceneRefs.length),
  )
  const parsed = useMemo(
    () => parsePhase32Screenplay(draft.payload),
    [draft.payload],
  )
  const editMode = useArtifactEditMode(
    draft.current?.editable ?? false,
    draft.current?.artifact_ref ?? "",
  )
  const contractError = parsed.error
    ? parsed.error
    : screenplayContractError(parsed.artifact, context.context)
  const loading = useLoadingPresence(
    runLoading || context.loading || (artifactAvailable && draft.loading),
  )

  useEffect(() => {
    const activeSceneChanged =
      Boolean(activeSceneRef) &&
      previousActiveSceneRef.current !== activeSceneRef
    previousActiveSceneRef.current = activeSceneRef
    if (activeSceneChanged) {
      setSelectedSceneRef(activeSceneRef)
      return
    }
    if (!selectedSceneRef || !orderedSceneRefs.includes(selectedSceneRef))
      setSelectedSceneRef(activeSceneRef || orderedSceneRefs[0] || "")
  }, [activeSceneRef, orderedSceneRefs, selectedSceneRef])

  if (!activeProject) return null
  if (loading.visible) {
    return (
      <BookLoader
        detail="读取 Scene 顺序、已接受版本、相关人物与当前正文块"
        label="正在同步剧本工作台"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <ScreenplayEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const status = activeRun.read_model.stage_status.script ?? "locked"
  const currentDecision = draft.current?.pending_decision ?? null
  const writebackRecovery = currentDecision?.kind === "writeback_recovery"
  const canDecide = Boolean(
    selectedSceneRef === activeSceneRef &&
      draft.current?.editable &&
      currentDecision?.domain_revision !== null,
  )
  const canRecoverWriteback = Boolean(
    selectedSceneRef === activeSceneRef &&
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
      setActionError("请先填写本场定向换稿的具体要求")
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
        if (nextStageId !== "script" && isProductionStageRoute(nextStageId))
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "剧本场景决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (!orderedSceneRefs.length) {
    return status === "running" ? (
      <BookLoader
        detail="系统将从已确认 Scene Deck 冻结场景顺序后逐场生成"
        label="正在准备剧本场次"
        variant="compact"
      />
    ) : (
      <ScreenplayEmptyState
        actionLabel="前往运行监控"
        detail={runError || "请先完成并确认剧本样片的场景调度。"}
        onAction={() => setRoute("run-monitor")}
        title="剧本正文尚未开始"
      />
    )
  }

  const selectedAccepted = Boolean(committedArtifactRefs[selectedSceneRef])
  const selectedSafe = selectedAccepted || writebackRecovery
  const revisionLabel = writebackRecovery
    ? `Scene ${orderedSceneRefs.indexOf(selectedSceneRef) + 1} · 已接受不可变版本 · 正式写回待恢复`
    : currentDecision
      ? `Scene ${orderedSceneRefs.indexOf(selectedSceneRef) + 1} · Revision ${currentDecision.domain_revision ?? "历史"} · 换稿 ${currentDecision.redraft_used ?? "-"}/${currentDecision.redraft_limit ?? "-"}`
      : selectedAccepted
        ? "已接受不可变版本"
        : "等待前序场次"

  return (
    <div className="screenplay-page-shell page-in">
      <header className="screenplay-toolbar">
        <div className="screenplay-toolbar-state">
          {selectedSafe ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {writebackRecovery
              ? "当前场次已接受 · 正式写回待恢复"
              : selectedAccepted
                ? "当前场次已接受"
                : canDecide
                  ? "当前场景等待作者决策"
                  : "场次尚未进入生成"}
          </span>
          <small>{draftStatusLabel(draft.status, artifactAvailable)}</small>
        </div>
        <div className="screenplay-actions">
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
                : `确认 S${String(orderedSceneRefs.indexOf(selectedSceneRef) + 1).padStart(2, "0")}`}
            </button>
          ) : activeTarget?.stage_id === "export" && selectedAccepted ? (
            <button
              className="btn btn-primary text-xs"
              onClick={() => setRoute("export")}
              type="button"
            >
              进入剧本交付 <Play size={12} />
            </button>
          ) : null}
        </div>
      </header>

      {(actionError || draft.error || context.error || runError) && (
        <div className="screenplay-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{actionError || draft.error || context.error || runError}</span>
        </div>
      )}

      {canRecoverWriteback ? (
        <WritebackRecoveryNotice
          busy={busy}
          onCancel={() => setDialog("cancel")}
          onRetry={() => void submitDecision("retry_writeback")}
          unitLabel={`Scene ${String(orderedSceneRefs.indexOf(selectedSceneRef) + 1).padStart(2, "0")}`}
        />
      ) : null}

      <ScreenplayArtifactEditor
        activeSceneRef={activeSceneRef}
        artifact={artifactAvailable ? parsed.artifact : null}
        artifactRef={draft.current?.artifact_ref ?? ""}
        committedArtifactRefs={committedArtifactRefs}
        editable={editMode.editing}
        onChange={draft.change}
        onSelectScene={setSelectedSceneRef}
        orderedSceneRefs={orderedSceneRefs}
        referenceContext={context.context}
        revisionLabel={revisionLabel}
        selectedSceneRef={selectedSceneRef || orderedSceneRefs[0]}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          busy={busy}
          direction={direction}
          error={actionError}
          id="phase32-screenplay-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留本场目标和结果，把说明性对白改成围绕档案盒归属的动作争夺，并让玛雅的语气更短、更克制。"
          regenerateDescription="只重写当前 Scene 正文；Scene 身份、顺序、场景标题、人物范围和上游调度保持冻结。"
          suggestions={[
            "减少解释性对白，让信息通过动作、停顿和可见选择落地。",
            "强化本场目标与对抗，但不要提前消费下一场结果。",
            "保持人物既定说话差异，收紧重复语句和无效寒暄。",
          ]}
        />
      ) : null}
    </div>
  )
}

function ScreenplayEmptyState({
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
    <div className="screenplay-empty page-in">
      <Film size={22} />
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
  if (!available) return "等待生成"
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
