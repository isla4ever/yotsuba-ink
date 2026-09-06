import { useMemo, useState } from "react"
import "../../../styles/phase32-cast.css"
import {
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Lock,
  Play,
  Sparkles,
  UsersRound,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { castRoutePresentation, parsePhase32Cast } from "../lib/phase32Cast"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePlanningArtifactAmendment } from "../state/usePlanningArtifactAmendment"
import { ArtifactAmendmentPanel } from "./ArtifactAmendmentPanel"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import { CastArtifactEditor } from "./CastArtifactEditor"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

export default function CastStageView() {
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
    activeRun?.read_model.artifact_refs.cast ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "cast",
      ),
  )
  const draft = usePhase32ArtifactDraft(
    runId,
    "cast",
    activeRun?.read_model.updated_at ?? "",
    artifactAvailable,
  )
  const amendment = usePlanningArtifactAmendment("cast", draft.current)
  const amendmentActive = amendment.flow.phase !== "idle"
  const editMode = useArtifactEditMode(
    Boolean(
      draft.current?.editable || amendment.flow.canStart || amendmentActive,
    ),
    draft.current?.artifact_ref ?? "",
  )
  const workingPayload = amendment.flow.payload ?? draft.payload
  const parsed = useMemo(
    () => parsePhase32Cast(workingPayload),
    [workingPayload],
  )
  const loading = useLoadingPresence(runLoading || draft.loading)
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
        detail="读取人物身份、关系聚合与当前作者草稿"
        label="正在同步人物圣经"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <CastEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const routeId = activeRun.definition.route_contract.creation_route_id
  const status = activeRun.read_model.stage_status.cast ?? "locked"
  const decision = draft.current?.pending_decision ?? null
  const canDecide = Boolean(
    draft.current?.editable && decision?.domain_revision !== null,
  )
  const busy = actionState !== "idle"
  const activeTarget = activeRun.read_model.stage_manifest.find(
    (item) => item.stage_id === activeRun.read_model.active_stage_id,
  )
  const routeCopy = castRoutePresentation(routeId)

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!decision || decision.domain_revision === null || busy) return
    if (action === "accept" && (!parsed.artifact || parsed.error)) {
      setActionError(parsed.error || "当前人物圣经未通过界面合同校验")
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
        if (nextStageId !== "cast" && isProductionStageRoute(nextStageId))
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "人物圣经决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (draft.status === "empty" || !draft.current || !parsed.artifact) {
    const generating = status === "running"
    return generating ? (
      <BookLoader
        detail="候选稿通过人物合同校验后会进入作者决策"
        label="正在生成人物圣经"
        variant="compact"
      />
    ) : (
      <CastEmptyState
        actionLabel="前往运行监控"
        detail={
          draft.error ||
          parsed.error ||
          runError ||
          "请先完成当前路线的人物上游规划阶段。"
        }
        onAction={() => setRoute("run-monitor")}
        title="人物圣经尚未生成"
      />
    )
  }

  const revisionLabel = decision
    ? `Revision ${decision.domain_revision ?? "历史"} · 换稿 ${decision.redraft_used ?? "-"}/${decision.redraft_limit ?? "-"}`
    : "已确认版本"
  const suggestions =
    routeId === "screenplay_sample"
      ? [
          "让每个人物目标都能在屏幕行动中被看见。",
          "拉开主要人物的对白声纹与应激反应。",
          "强化关系压力如何触发下一次可见选择。",
        ]
      : routeId === "long_novel"
        ? [
            "区分人物在全书、Part 与卷册中的长期职责。",
            "让关系变化条件能够跨卷持续推进而不提前兑现。",
            "检查人物限制是否足以支撑长期冲突而非一次性障碍。",
          ]
        : [
            "删除不承担戏剧任务的人物，集中有限篇幅。",
            "让欲望、代价与单体弧线形成明确差异。",
            "强化关键关系在结尾前必须发生的变化触发。",
          ]

  return (
    <div className="phase32-cast-page page-in">
      <header className="phase32-cast-toolbar">
        <div className="phase32-cast-toolbar-state">
          {draft.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {draft.current.status === "committed"
              ? "人物圣经已定稿"
              : canDecide
                ? "候选聚合等待作者决策"
                : "历史决策只读"}
          </span>
          <small>{draftStatusLabel(draft.status)}</small>
        </div>
        <div className="phase32-cast-actions">
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
              {actionState === "accepting" ? "正在定稿…" : "确认人物圣经"}
            </button>
          ) : amendment.flow.phase === "idle" &&
            activeTarget &&
            activeTarget.stage_id !== "cast" &&
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

      {(actionError || draft.error || parsed.error || runError) && (
        <div className="phase32-cast-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{actionError || draft.error || parsed.error || runError}</span>
        </div>
      )}

      <CastArtifactEditor
        artifact={parsed.artifact}
        artifactRef={draft.current.artifact_ref}
        editable={editMode.editing}
        onChange={changeArtifact}
        revisionLabel={revisionLabel}
        routeId={routeId}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          busy={busy}
          direction={direction}
          error={actionError}
          id="phase32-cast-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留现有人物身份，让两位核心人物的欲望更冲突，并把关系变化触发落到一次可见选择。"
          regenerateDescription={`只重写人物文学字段与关系内容；subject ref 与人物集合保持冻结，新关系只能引用已登记人物。${routeCopy.nextUse}`}
          suggestions={suggestions}
        />
      ) : null}
    </div>
  )
}

function CastEmptyState({
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
    <div className="phase32-cast-empty page-in">
      <UsersRound size={22} />
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
