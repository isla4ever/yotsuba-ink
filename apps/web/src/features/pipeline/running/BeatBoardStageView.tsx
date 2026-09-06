import { useMemo, useState } from "react"
import "../../../styles/phase32-beat-board.css"
import "../../../styles/phase32-beat-board-editor.css"
import {
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  ListOrdered,
  Lock,
  Play,
  Sparkles,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { parsePhase32BeatBoard } from "../lib/phase32BeatBoard"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePhase32BeatBoardContext } from "../state/usePhase32BeatBoardContext"
import { usePlanningArtifactAmendment } from "../state/usePlanningArtifactAmendment"
import { ArtifactAmendmentPanel } from "./ArtifactAmendmentPanel"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import { BeatBoardArtifactEditor } from "./BeatBoardArtifactEditor"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

type BeatBoardEmptyStateProps = {
  actionLabel: string
  detail: string
  onAction: () => void
  title: string
}

export default function BeatBoardStageView() {
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
    activeRun?.read_model.artifact_refs.beat_board ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "beat_board",
      ),
  )
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const draft = usePhase32ArtifactDraft(
    runId,
    "beat_board",
    authorityRevision,
    artifactAvailable,
  )
  const amendment = usePlanningArtifactAmendment("beat_board", draft.current)
  const amendmentActive = amendment.flow.phase !== "idle"
  const editMode = useArtifactEditMode(
    Boolean(
      draft.current?.editable || amendment.flow.canStart || amendmentActive,
    ),
    draft.current?.artifact_ref ?? "",
  )
  const context = usePhase32BeatBoardContext(
    runId,
    authorityRevision,
    artifactAvailable,
  )
  const workingPayload = amendment.flow.payload ?? draft.payload
  const parsed = useMemo(
    () => parsePhase32BeatBoard(workingPayload),
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
        detail="读取样片承诺、已确认人物、节拍顺序与当前作者草稿"
        label="正在同步屏幕决策节拍"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <BeatBoardEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const status = activeRun.read_model.stage_status.beat_board ?? "locked"
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
      setActionError(parsed.error || "当前因果节拍未通过界面合同校验")
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
        if (nextStageId !== "beat_board" && isProductionStageRoute(nextStageId))
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "因果节拍决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (draft.status === "empty" || !draft.current || !parsed.artifact) {
    const generating = status === "running"
    return generating ? (
      <BookLoader
        detail="候选节拍通过格式与冻结身份合同后会进入作者决策"
        label="正在生成屏幕决策节拍"
        variant="compact"
      />
    ) : (
      <BeatBoardEmptyState
        actionLabel="前往运行监控"
        detail={
          draft.error ||
          parsed.error ||
          runError ||
          "请先完成剧本样片 Brief 与人物圣经。"
        }
        onAction={() => setRoute("run-monitor")}
        title="因果节拍尚未生成"
      />
    )
  }

  const revisionLabel = decision
    ? `Revision ${decision.domain_revision ?? "历史"} · 换稿 ${decision.redraft_used ?? "-"}/${decision.redraft_limit ?? "-"}`
    : "已确认版本"

  return (
    <div className="beat-board-page page-in">
      <header className="beat-board-toolbar">
        <div className="beat-board-toolbar-state">
          {draft.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {draft.current.status === "committed"
              ? "因果节拍已定稿"
              : canDecide
                ? "候选节拍等待作者决策"
                : "历史决策只读"}
          </span>
          <small>{draftStatusLabel(draft.status)}</small>
        </div>
        <div className="beat-board-actions">
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
              {actionState === "accepting" ? "正在定稿…" : "确认因果节拍"}
            </button>
          ) : amendment.flow.phase === "idle" &&
            activeTarget &&
            activeTarget.stage_id !== "beat_board" &&
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
        <div className="beat-board-alert" role="alert">
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

      <BeatBoardArtifactEditor
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
          id="phase32-beat-board-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留签名链，让中段 Beat 从被动发现改为主角在公开证人和保护线人之间作出可见选择。"
          regenerateDescription="重新生成可见压力、台面决定、结果和 setup/payoff 覆盖；已确认 Brief 与人物名册保持上游权威。"
          suggestions={[
            "让每个 Beat 都由角色决定改变局面，不以信息解释代替行动。",
            "检查上一拍结果是否能直接制造下一拍可见压力。",
            "让 setup/payoff 在样片时长内形成清晰覆盖，不机械平均节拍。",
          ]}
        />
      ) : null}
    </div>
  )
}

function BeatBoardEmptyState({
  actionLabel,
  detail,
  onAction,
  title,
}: BeatBoardEmptyStateProps) {
  return (
    <div className="beat-board-empty page-in">
      <ListOrdered size={22} />
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
      clean: "原始候选",
      dirty: "等待自动保存",
      saving: "正在保存",
      saved: "草稿已保存",
      readonly: "权威版本",
      error: "草稿异常",
    } as Record<string, string>)[status] ?? ""
  )
}
