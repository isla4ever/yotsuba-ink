import { useMemo, useState } from "react"
import "../../../styles/phase32-section-plan.css"
import "../../../styles/phase32-section-plan-editor.css"
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
import { parsePhase32SectionPlan } from "../lib/phase32SectionPlan"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { usePhase32SectionPlanContext } from "../state/usePhase32SectionPlanContext"
import { usePlanningArtifactAmendment } from "../state/usePlanningArtifactAmendment"
import { ArtifactAmendmentPanel } from "./ArtifactAmendmentPanel"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { SectionPlanArtifactEditor } from "./SectionPlanArtifactEditor"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

export default function SectionPlanStageView() {
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
    activeRun?.read_model.artifact_refs.section_plan ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "section_plan",
      ),
  )
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const draft = usePhase32ArtifactDraft(
    runId,
    "section_plan",
    authorityRevision,
    artifactAvailable,
  )
  const amendment = usePlanningArtifactAmendment("section_plan", draft.current)
  const amendmentActive = amendment.flow.phase !== "idle"
  const editMode = useArtifactEditMode(
    Boolean(
      draft.current?.editable || amendment.flow.canStart || amendmentActive,
    ),
    draft.current?.artifact_ref ?? "",
  )
  const context = usePhase32SectionPlanContext(
    runId,
    authorityRevision,
    artifactAvailable,
  )
  const workingPayload = amendment.flow.payload ?? draft.payload
  const parsed = useMemo(
    () => parsePhase32SectionPlan(workingPayload),
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
        detail="读取正文单元、人物 POV、Promise 覆盖与当前作者草稿"
        label="正在同步章节与段落计划"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <SectionPlanEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const status = activeRun.read_model.stage_status.section_plan ?? "locked"
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
      setActionError(parsed.error || "当前章节计划未通过界面合同校验")
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
          nextStageId !== "section_plan" &&
          isProductionStageRoute(nextStageId)
        )
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "章节计划决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (draft.status === "empty" || !draft.current || !parsed.artifact) {
    const generating = status === "running"
    return generating ? (
      <BookLoader
        detail="候选计划通过 Story Map 与 Cast 引用合同后会进入作者决策"
        label="正在生成章节与段落计划"
        variant="compact"
      />
    ) : (
      <SectionPlanEmptyState
        actionLabel="前往运行监控"
        detail={
          draft.error ||
          parsed.error ||
          runError ||
          "请先完成短中篇 Story Map 与人物圣经。"
        }
        onAction={() => setRoute("run-monitor")}
        title="章节与段落计划尚未生成"
      />
    )
  }

  const revisionLabel = decision
    ? `Revision ${decision.domain_revision ?? "历史"} · 换稿 ${decision.redraft_used ?? "-"}/${decision.redraft_limit ?? "-"}`
    : "已确认版本"

  return (
    <div className="section-plan-page page-in">
      <header className="section-plan-toolbar">
        <div className="section-plan-toolbar-state">
          {draft.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {draft.current.status === "committed"
              ? "章节计划已定稿"
              : canDecide
                ? "候选计划等待作者决策"
                : "历史决策只读"}
          </span>
          <small>{draftStatusLabel(draft.status)}</small>
        </div>
        <div className="section-plan-actions">
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
              {actionState === "accepting" ? "正在定稿…" : "确认章节计划"}
            </button>
          ) : amendment.flow.phase === "idle" &&
            activeTarget &&
            activeTarget.stage_id !== "section_plan" &&
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
        <div className="section-plan-alert" role="alert">
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

      <SectionPlanArtifactEditor
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
          id="phase32-section-plan-dialog"
          kind={dialog}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
          placeholder="例如：保留调查主线，让第三单元从解释证据改为迫使主角在公开与保护证人之间作出选择。"
          regenerateDescription="重新规划正文单元的任务、POV、场景负载、交接和软字数；已确认 Story Map 与人物注册表保持上游权威。"
          suggestions={[
            "让每个单元都改变局面，不重复调查或解释同一条信息。",
            "检查上一单元 handoff 是否能直接驱动下一单元开场。",
            "按戏剧任务分配软字数，不把字数目标变成硬性填充。",
          ]}
        />
      ) : null}
    </div>
  )
}

function SectionPlanEmptyState({
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
    <div className="section-plan-empty page-in">
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
