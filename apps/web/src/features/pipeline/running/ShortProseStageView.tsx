import { useEffect, useMemo, useRef, useState } from "react"
import "../../../styles/phase32-short-prose.css"
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
  parsePhase32ShortProse,
  projectShortProseUnitKind,
  shortProseContractError,
} from "../lib/phase32ShortProse"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePhase32ShortProseContext } from "../state/usePhase32ShortProseContext"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { ShortProseWorkbench } from "./ShortProseWorkbench"
import { WritebackRecoveryNotice } from "./WritebackRecoveryNotice"

type ActionState = "idle" | "accepting" | "regenerating" | "retrying-writeback" | "cancelling"

export default function ShortProseStageView() {
  const {
    activeProject,
    activeRun,
    reconnectRun,
    refreshRun,
    runError,
    runLoading,
    setRoute,
  } = useApp()
  const [selectedUnitRef, setSelectedUnitRef] = useState("")
  const [dialog, setDialog] = useState<Phase32DecisionDialogKind | null>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] = useState<ActionState>("idle")
  const [actionError, setActionError] = useState("")
  const previousActiveUnitRef = useRef("")
  const runId = activeRun?.definition.run_id ?? ""
  const progress = activeRun?.read_model.sequential_stage_progress.text
  const orderedUnitRefs = progress?.ordered_unit_refs ?? []
  const committedArtifactRefs = progress?.committed_artifact_refs ?? {}
  const decision = activeRun?.read_model.pending_decisions.find(
    (item) => item.stage_id === "text",
  )
  const activeUnitRef =
    decision?.unit_ref || activeRun?.read_model.active_unit_ref || ""
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const artifactAvailable = Boolean(
    selectedUnitRef &&
      (committedArtifactRefs[selectedUnitRef] ||
        decision?.unit_ref === selectedUnitRef),
  )
  const draft = usePhase32ArtifactDraft(
    runId,
    "text",
    authorityRevision,
    artifactAvailable,
    selectedUnitRef,
  )
  const context = usePhase32ShortProseContext(
    runId,
    authorityRevision,
    Boolean(runId && orderedUnitRefs.length),
  )
  const parsed = useMemo(
    () => parsePhase32ShortProse(draft.payload),
    [draft.payload],
  )
  const expectedUnitKind = projectShortProseUnitKind(
    activeRun?.definition.scale_profile.payload ?? {},
  )
  const editMode = useArtifactEditMode(
    draft.current?.editable ?? false,
    draft.current?.artifact_ref ?? "",
  )
  const contractError = parsed.error
    ? parsed.error
    : shortProseContractError(
        parsed.artifact,
        context.context,
        selectedUnitRef,
        expectedUnitKind,
      )
  const loading = useLoadingPresence(
    runLoading || context.loading || (artifactAvailable && draft.loading),
  )

  useEffect(() => {
    const activeUnitChanged =
      Boolean(activeUnitRef) && previousActiveUnitRef.current !== activeUnitRef
    previousActiveUnitRef.current = activeUnitRef
    if (activeUnitChanged) {
      setSelectedUnitRef(activeUnitRef)
      return
    }
    if (!selectedUnitRef || !orderedUnitRefs.includes(selectedUnitRef))
      setSelectedUnitRef(activeUnitRef || orderedUnitRefs[0] || "")
  }, [activeUnitRef, orderedUnitRefs, selectedUnitRef])

  if (!activeProject) return null
  if (loading.visible) {
    return (
      <BookLoader
        detail="读取单元顺序、已接受版本、当前计划与有限连续性交接"
        label="正在同步正文写作台"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <ShortProseEmptyState
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
    selectedUnitRef === activeUnitRef &&
      draft.current?.editable &&
      currentDecision?.domain_revision !== null,
  )
  const canRecoverWriteback = Boolean(
    selectedUnitRef === activeUnitRef &&
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
      setActionError("请先填写当前正文单元的定向换稿要求")
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
        reason instanceof Error ? reason.message : "正文单元决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (!orderedUnitRefs.length) {
    return status === "running" ? (
      <BookLoader
        detail="系统会从已确认 Section Plan 冻结顺序后逐单元生成"
        label="正在准备正文单元"
        variant="compact"
      />
    ) : (
      <ShortProseEmptyState
        actionLabel="前往运行监控"
        detail={runError || "请先完成并确认短中篇的章节与段落计划。"}
        onAction={() => setRoute("run-monitor")}
        title="正文尚未开始"
      />
    )
  }

  const selectedAccepted = Boolean(committedArtifactRefs[selectedUnitRef])
  const selectedSafe = selectedAccepted || writebackRecovery
  const revisionLabel = writebackRecovery
    ? `U${String(orderedUnitRefs.indexOf(selectedUnitRef) + 1).padStart(2, "0")} · 已接受不可变版本 · 正式写回待恢复`
    : currentDecision
      ? `U${String(orderedUnitRefs.indexOf(selectedUnitRef) + 1).padStart(2, "0")} · Revision ${currentDecision.domain_revision ?? "历史"} · 换稿 ${currentDecision.redraft_used ?? "-"}/${currentDecision.redraft_limit ?? "-"}`
      : selectedAccepted
        ? "已接受不可变版本"
        : "等待前序单元"

  return (
    <div className="short-prose-page page-in">
      <header className="short-prose-toolbar">
        <div className="short-prose-toolbar-state">
          {selectedSafe ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {writebackRecovery
              ? "当前正文已接受 · 正式写回待恢复"
              : selectedAccepted
                ? "当前正文已接受"
                : canDecide
                  ? "当前单元等待作者决策"
                  : "单元尚未进入生成"}
          </span>
          <small>{draftStatusLabel(draft.status, artifactAvailable)}</small>
        </div>
        <div className="short-prose-actions">
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
                : `确认 U${String(orderedUnitRefs.indexOf(selectedUnitRef) + 1).padStart(2, "0")}`}
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
        <div className="short-prose-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{actionError || draft.error || context.error || runError}</span>
        </div>
      )}

      {canRecoverWriteback ? (
        <WritebackRecoveryNotice
          busy={busy}
          onCancel={() => setDialog("cancel")}
          onRetry={() => void submitDecision("retry_writeback")}
          unitLabel={`U${String(orderedUnitRefs.indexOf(selectedUnitRef) + 1).padStart(2, "0")}`}
        />
      ) : null}

      <ShortProseWorkbench
        activeUnitRef={activeUnitRef}
        artifact={artifactAvailable ? parsed.artifact : null}
        artifactRef={draft.current?.artifact_ref ?? ""}
        committedArtifactRefs={committedArtifactRefs}
        editable={editMode.editing}
        expectedUnitKind={expectedUnitKind}
        onChange={draft.change}
        onSelectUnit={setSelectedUnitRef}
        orderedUnitRefs={orderedUnitRefs}
        referenceContext={context.context}
        revisionLabel={revisionLabel}
        selectedUnitRef={selectedUnitRef || orderedUnitRefs[0]}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          busy={busy}
          direction={direction}
          error={actionError}
          id="phase32-short-prose-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留本单元的证据发现与结尾交接，删去解释性总结，让玛雅通过动作和对话逐步确认时间戳矛盾。"
          regenerateDescription="只重写当前正文单元；单元身份、标题、POV、计划顺序与已接受前缀保持冻结。"
          suggestions={[
            "保留戏剧任务和交接结果，减少概述式说明与重复心理复述。",
            "让场景动作承担信息推进，不提前消费下一单元的揭示。",
            "保持当前 POV 的观察边界和人物既定声音。",
          ]}
        />
      ) : null}
    </div>
  )
}

function ShortProseEmptyState({
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
    <div className="short-prose-empty page-in">
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
