import { useMemo, useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Lock,
  Play,
  Save,
  Sparkles,
} from "lucide-react"
import type { Route } from "../contracts/app"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { parsePhase32Brief } from "../lib/phase32Brief"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "../running/Phase32StageDecisionDialog"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { ArtifactModeSwitch } from "../running/ArtifactModeSwitch"
import { ArtifactAmendmentPanel } from "../running/ArtifactAmendmentPanel"
import { usePlanningArtifactAmendment } from "../state/usePlanningArtifactAmendment"
import { Phase32BriefArtifactForm } from "./Phase32BriefArtifactForm"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

export default function Phase32BriefStageView() {
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
  const briefArtifactAvailable = Boolean(
    activeRun?.read_model.artifact_refs.brief ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "brief",
      ),
  )
  const draft = usePhase32ArtifactDraft(
    runId,
    "brief",
    activeRun?.read_model.updated_at ?? "",
    briefArtifactAvailable,
  )
  const amendment = usePlanningArtifactAmendment("brief", draft.current)
  const amendmentActive = amendment.flow.phase !== "idle"
  const editMode = useArtifactEditMode(
    Boolean(
      draft.current?.editable || amendment.flow.canStart || amendmentActive,
    ),
    draft.current?.artifact_ref ?? "",
  )
  const workingPayload = amendment.flow.payload ?? draft.payload
  const parsed = useMemo(
    () =>
      parsePhase32Brief(
        activeRun?.definition.route_contract.creation_route_id ??
          activeProject?.creationRouteId ??
          "short_novel",
        workingPayload,
      ),
    [activeProject?.creationRouteId, activeRun, workingPayload],
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
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在同步创作立项"
        detail="读取候选稿、作者草稿与决策边界"
      />
    )
  }
  if (!activeRun) {
    return (
      <BriefEmptyState
        title="Run 尚未就绪"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        actionLabel="返回作品库"
        onAction={() => setRoute("studio")}
      />
    )
  }

  const stage = activeRun.read_model.stage_manifest.find(
    (item) => item.stage_id === "brief",
  )
  const status = activeRun.read_model.stage_status.brief ?? "locked"
  const decision = draft.current?.pending_decision ?? null
  const canDecide = Boolean(
    draft.current?.editable && decision?.domain_revision !== null,
  )
  const busy = actionState !== "idle"
  const nextStage = activeRun.read_model.stage_manifest.find(
    (item) => item.ordinal === (stage?.ordinal ?? 0) + 1,
  )
  const frozenIntent = activeRun.definition.inputs.payload.creative_intent
  const intent =
    typeof frozenIntent === "string" ? frozenIntent : activeProject.subtitle

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!decision || decision.domain_revision === null || busy) return
    if (action === "accept" && (!parsed.artifact || parsed.error)) {
      setActionError(parsed.error || "当前 Brief 未通过界面合同校验")
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
      await resolvePhase32RunDecision(activeRun.definition.run_id, {
        decisionId: decision.decision_id,
        action,
        domainRevision: decision.domain_revision,
        direction: action === "regenerate" ? direction : undefined,
        draftRef: draftRef || undefined,
      })
      setDialog(null)
      setDirection("")
      await refreshRun()
      reconnectRun()
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "Brief 决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (draft.status === "empty" || !draft.current || !parsed.artifact) {
    const generating = status === "running"
    return generating ? (
      <BookLoader
        variant="compact"
        label="正在生成创作立项"
        detail="候选稿通过结构校验后会在这里进入作者决策"
      />
    ) : (
      <BriefEmptyState
        title="创作立项尚未生成"
        detail={
          draft.error || parsed.error || runError || "请先启动当前创作流水线。"
        }
        actionLabel="前往运行监控"
        onAction={() => setRoute("run-monitor")}
      />
    )
  }

  return (
    <div className="phase32-brief-page page-in">
      <header className="phase32-brief-toolbar">
        <div className="phase32-brief-toolbar-state">
          {draft.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {draft.current.status === "committed"
              ? "立项已定稿"
              : canDecide
                ? "候选稿等待作者决策"
                : "历史决策只读"}
          </span>
          <small>{draftStatusLabel(draft.status)}</small>
        </div>
        <div className="phase32-brief-actions">
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
              type="button"
              className="btn btn-secondary text-xs"
              disabled={busy}
              onClick={() => setDialog("regenerate")}
            >
              <Sparkles size={12} /> 定向换稿
            </button>
          ) : null}
          {canDecide && decision?.allowed_actions.includes("cancel") ? (
            <button
              type="button"
              className="btn btn-ghost text-risk text-xs"
              disabled={busy}
              onClick={() => setDialog("cancel")}
            >
              <CircleStop size={12} /> 取消
            </button>
          ) : null}
          {canDecide && decision?.allowed_actions.includes("accept") ? (
            <button
              type="button"
              className="btn btn-primary text-xs"
              disabled={busy || draft.status === "error"}
              onClick={() => void submitDecision("accept")}
            >
              <Lock size={12} />
              {actionState === "accepting" ? "正在定稿…" : "确认立项"}
            </button>
          ) : amendment.flow.phase === "idle" &&
            nextStage &&
            draft.current.status === "committed" ? (
            <button
              type="button"
              className="btn btn-primary text-xs"
              onClick={() => setRoute(nextStage.stage_id as Route)}
            >
              {nextStage.label} <ArrowRight size={12} />
            </button>
          ) : null}
        </div>
      </header>

      {(actionError || draft.error || runError) && (
        <div className="phase32-brief-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{actionError || draft.error || runError}</span>
        </div>
      )}

      <div className="phase32-brief-scroll">
        <main className="phase32-brief-workbench">
          <div className="phase32-brief-title">
            <div>
              <span>PHASE 32 · {activeRun.summary.route_label}</span>
              <h1>{stage?.label ?? "创作立项"}</h1>
            </div>
            <div>
              <Save size={12} />
              <span>
                {editMode.editing
                  ? draft.current.editable
                    ? "编辑自动保存为当前决策草稿"
                    : "正在编辑正式修订副本 · 尚未改变旧 Run"
                  : draft.current.editable
                    ? "阅读模式 · 切换编辑后可修改候选稿"
                    : amendment.flow.canStart
                      ? "已确认版本 · 可发起正式修订"
                      : "已确认版本 · 只读"}
              </span>
            </div>
          </div>

          <div className="phase32-brief-layout">
            <div
              className={`phase32-brief-editor artifact-mode-surface ${
                editMode.editing ? "is-editing" : "is-viewing"
              }`}
            >
              <Phase32BriefArtifactForm
                artifact={parsed.artifact}
                editable={editMode.editing}
                onChange={changeArtifact}
              />
            </div>
            <aside
              className="phase32-brief-inspector"
              aria-label="冻结创作约束"
            >
              <section>
                <span>冻结规模</span>
                <strong>{targetLabel(parsed.artifact.value)}</strong>
                <small>改变目标需要新建 Run，当前稿不能覆盖冻结输入。</small>
              </section>
              <section>
                <span>创作意图</span>
                <p>{intent}</p>
              </section>
              <section>
                <span>版本来源</span>
                <code title={draft.current.artifact_ref}>
                  {shortRef(draft.current.artifact_ref)}
                </code>
                {decision ? (
                  <small>
                    Revision {decision.domain_revision ?? "历史"} · 换稿{" "}
                    {decision.redraft_used ?? "-"}/
                    {decision.redraft_limit ?? "-"}
                  </small>
                ) : null}
              </section>
            </aside>
          </div>
        </main>
      </div>

      {dialog ? (
        <Phase32StageDecisionDialog
          id="phase32-brief-dialog"
          kind={dialog}
          busy={busy}
          direction={direction}
          error={actionError}
          regenerateDescription="只描述需要改变的方向。模型会沿当前路线、规模与上下文重新生成 Brief。"
          placeholder="例如：把核心两难前置，让结尾代价更不可逆。"
          suggestions={[
            "把核心两难前置，并明确不可逆代价。",
            "减少背景解释，强化故事独有的读者承诺。",
            "让结尾方向更具体，并保留一个可继续追问的问题。",
          ]}
          onClose={() => !busy && setDialog(null)}
          onDirectionChange={setDirection}
          onSubmit={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
        />
      ) : null}
    </div>
  )
}

function BriefEmptyState({
  title,
  detail,
  actionLabel,
  onAction,
}: {
  title: string
  detail: string
  actionLabel: string
  onAction: () => void
}) {
  return (
    <div className="phase32-brief-empty page-in">
      <FilePenLine size={22} />
      <h1>{title}</h1>
      <p>{detail}</p>
      <button
        type="button"
        className="btn btn-secondary text-xs"
        onClick={onAction}
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

function targetLabel(value: {
  target_minutes?: number
  target_characters?: number
}) {
  return value.target_minutes
    ? `${value.target_minutes} 分钟`
    : `${(value.target_characters ?? 0).toLocaleString("zh-CN")} 字`
}

function shortRef(value: string) {
  return value.length > 34 ? `${value.slice(0, 20)}…${value.slice(-10)}` : value
}
