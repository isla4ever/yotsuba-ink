import { useMemo, useState } from "react"
import "../../../styles/phase32-rolling-detail.css"
import "../../../styles/phase32-rolling-detail-editor.css"
import {
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Lock,
  MapPinned,
  Play,
  Sparkles,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { parsePhase32RollingDetail } from "../lib/phase32RollingDetail"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePhase32RollingDetailContext } from "../state/usePhase32RollingDetailContext"
import { usePlanningArtifactAmendment } from "../state/usePlanningArtifactAmendment"
import { ArtifactAmendmentPanel } from "./ArtifactAmendmentPanel"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { RollingDetailArtifactEditor } from "./RollingDetailArtifactEditor"
import { ContractRepairWorkbench } from "./ContractRepairWorkbench"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

export default function RollingDetailStageView() {
  const {
    activeProject,
    activeRun,
    reconnectRun,
    refreshRun,
    runError,
    runLoading,
    setRoute,
  } = useApp()
  const [dialog, setDialog] = useState<Phase32DecisionDialogKind | null>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] = useState<ActionState>("idle")
  const [actionError, setActionError] = useState("")
  const runId = activeRun?.definition.run_id ?? ""
  const artifactAvailable = Boolean(
    activeRun?.read_model.artifact_refs.rolling_detail ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "rolling_detail",
      ),
  )
  const contractFailure = Boolean(
    activeRun?.read_model.status === "failed" &&
      activeRun.read_model.failure?.code === "provider_contract_failed" &&
      activeRun.read_model.failure.stage_id === "rolling_detail",
  )
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const draft = usePhase32ArtifactDraft(
    runId,
    "rolling_detail",
    authorityRevision,
    artifactAvailable,
  )
  const amendment = usePlanningArtifactAmendment(
    "rolling_detail",
    draft.current,
  )
  const amendmentActive = amendment.flow.phase !== "idle"
  const editMode = useArtifactEditMode(
    Boolean(
      draft.current?.editable || amendment.flow.canStart || amendmentActive,
    ),
    draft.current?.artifact_ref ?? "",
  )
  const context = usePhase32RollingDetailContext(
    runId,
    authorityRevision,
    artifactAvailable || contractFailure,
  )
  const workingPayload = amendment.flow.payload ?? draft.payload
  const parsed = useMemo(
    () => parsePhase32RollingDetail(workingPayload),
    [workingPayload],
  )
  const loading = useLoadingPresence(
    runLoading || draft.loading || context.loading,
  )
  const editArtifact = () => {
    if (!draft.current?.editable && amendment.flow.phase === "idle")
      amendment.flow.begin()
    editMode.edit()
  }
  const changeArtifact = amendmentActive ? amendment.flow.change : draft.change

  if (!activeProject) return null
  if (loading.visible) {
    return (
      <BookLoader
        detail="读取当前 Window、章节蓝图、场景施工单与作者草稿"
        label="正在同步滚动细纲"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <RollingDetailEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const status = activeRun.read_model.stage_status.rolling_detail ?? "locked"

  if (contractFailure) {
    return (
      <ContractRepairWorkbench
        onRestored={async () => {
          await refreshRun()
          reconnectRun()
        }}
        referenceContext={context.context}
        referenceContextError={context.error}
        run={activeRun}
      />
    )
  }

  const decision = draft.current?.pending_decision ?? null
  const canDecide = Boolean(
    draft.current?.editable && decision?.domain_revision !== null,
  )
  const busy = actionState !== "idle"
  const activeTarget = activeRun.read_model.stage_manifest.find(
    (item) => item.stage_id === activeRun.read_model.active_stage_id,
  )

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!decision || decision.domain_revision === null || busy) return
    if (action === "accept" && (!parsed.artifact || parsed.error)) {
      setActionError(parsed.error || "当前滚动细纲未通过界面合同校验")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次定向换稿的具体要求")
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
      const draftRef = action === "accept" ? await draft.flush() : ""
      const resolved = await resolvePhase32RunDecision(
        activeRun.definition.run_id,
        {
          decisionId: decision.decision_id,
          action,
          domainRevision: decision.domain_revision,
          direction: action === "regenerate" ? direction : undefined,
          draftRef: draftRef || undefined,
        },
      )
      setDialog(null)
      setDirection("")
      await refreshRun()
      reconnectRun()
      if (action === "accept") {
        const nextStageId = resolved.read_model.active_stage_id
        if (
          nextStageId !== "rolling_detail" &&
          isProductionStageRoute(nextStageId)
        )
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "滚动细纲决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (draft.status === "empty" || !draft.current || !parsed.artifact) {
    const generating = status === "running"
    return generating ? (
      <BookLoader
        detail="候选聚合通过 Volume、Cast 与 POV 引用合同后会进入作者决策"
        label="正在生成滚动细纲"
        variant="compact"
      />
    ) : (
      <RollingDetailEmptyState
        actionLabel="前往运行监控"
        detail={
          draft.error ||
          parsed.error ||
          runError ||
          "请先完成长篇 Book Architecture、Cast 与 Volumes。"
        }
        onAction={() => setRoute("run-monitor")}
        title="滚动细纲尚未生成"
      />
    )
  }

  const revisionLabel = decision
    ? `Revision ${decision.domain_revision ?? "历史"} · 换稿 ${decision.redraft_used ?? "-"}/${decision.redraft_limit ?? "-"}`
    : "已确认版本"

  return (
    <div className="phase32-detail-page page-in">
      <header className="phase32-detail-toolbar">
        <div className="phase32-detail-toolbar-state">
          {draft.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {draft.current.status === "committed"
              ? "滚动细纲已定稿"
              : canDecide
                ? "当前 Window 等待作者决策"
                : "历史决策只读"}
          </span>
          <small>{draftStatusLabel(draft.status)}</small>
        </div>
        <div className="phase32-detail-actions">
          <ArtifactModeSwitch
            canEdit={Boolean(
              draft.current.editable ||
                amendment.flow.canStart ||
                amendmentActive,
            )}
            editLabel={draft.current.editable ? "编辑" : "修订"}
            editTitle={
              draft.current.editable ? "编辑候选稿" : "正式修订已提交版本"
            }
            editing={editMode.editing}
            onEdit={editArtifact}
            onShow={editMode.show}
          />
          <ArtifactAmendmentPanel
            flow={amendment.flow}
            manifest={activeRun.read_model.stage_manifest}
            onEnterSuccessor={amendment.enterSuccessor}
            sourceRunId={runId}
          />
          {canDecide && decision?.allowed_actions.includes("regenerate") ? (
            <button
              className="btn btn-secondary text-xs"
              disabled={busy}
              onClick={() => setDialog("regenerate")}
              type="button"
            >
              <Sparkles size={12} /> 定向换稿
            </button>
          ) : null}
          {canDecide && decision?.allowed_actions.includes("cancel") ? (
            <button
              className="btn btn-ghost text-risk text-xs"
              disabled={busy}
              onClick={() => setDialog("cancel")}
              type="button"
            >
              <CircleStop size={12} /> 取消
            </button>
          ) : null}
          {canDecide && decision?.allowed_actions.includes("accept") ? (
            <button
              className="btn btn-primary text-xs"
              disabled={
                busy || draft.status === "error" || Boolean(parsed.error)
              }
              onClick={() => void submitDecision("accept")}
              type="button"
            >
              <Lock size={12} />
              {actionState === "accepting" ? "正在定稿…" : "确认当前细纲"}
            </button>
          ) : amendment.flow.phase === "idle" &&
            activeTarget &&
            activeTarget.stage_id !== "rolling_detail" &&
            draft.current.status === "committed" ? (
            <button
              className="btn btn-primary text-xs"
              onClick={() => {
                if (isProductionStageRoute(activeTarget.stage_id))
                  setRoute(activeTarget.stage_id)
              }}
              type="button"
            >
              进入{activeTarget.label} <Play size={12} />
            </button>
          ) : null}
        </div>
      </header>

      {(actionError ||
        draft.error ||
        context.error ||
        parsed.error ||
        runError) && (
        <div className="phase32-detail-alert" role="alert">
          <AlertTriangle size={13} />
          <span>
            {actionError ||
              draft.error ||
              context.error ||
              parsed.error ||
              runError}
          </span>
        </div>
      )}

      <RollingDetailArtifactEditor
        artifact={parsed.artifact}
        artifactRef={draft.current.artifact_ref}
        editable={editMode.editing}
        onChange={changeArtifact}
        referenceContext={context.context}
        revisionLabel={revisionLabel}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          busy={busy}
          direction={direction}
          error={actionError}
          id="phase32-rolling-detail-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留 Window、章节与人物引用，让第二章不再重复取证，而是把职业代价变成公开听证中的不可逆选择。"
          regenerateDescription="只重写当前 Window 的章节施工、场景、状态和 handoff；Window、Chapter、Scene、Volume、POV 与人物范围保持冻结。"
          suggestions={[
            "让每章的进入与退出状态真正发生变化，减少重复调查动作。",
            "检查每个场景都有目标、对抗与可交给下一场的结果。",
            "强化章尾钩子与下一章 handoff，但不提前写正文或改动未来 Window。",
          ]}
        />
      ) : null}
    </div>
  )
}

function RollingDetailEmptyState({
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
    <div className="phase32-detail-empty page-in">
      <MapPinned size={22} />
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

function draftStatusLabel(status: string) {
  return (
    ({
      clean: "当前候选",
      dirty: "等待自动保存",
      saving: "正在保存",
      saved: "草稿已保存",
      readonly: "权威版本",
      error: "草稿异常",
    } as Record<string, string>)[status] ?? ""
  )
}
