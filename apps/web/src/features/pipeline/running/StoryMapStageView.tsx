import { useMemo, useState } from "react"
import "../../../styles/phase32-story-map.css"
import {
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  GitBranch,
  Lock,
  Play,
  Sparkles,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { parsePhase32StoryMap } from "../lib/phase32StoryMap"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { useArtifactEditMode } from "../state/useArtifactEditMode"
import { usePhase32ArtifactDraft } from "../state/usePhase32ArtifactDraft"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
import { ArtifactAmendmentPanel } from "./ArtifactAmendmentPanel"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { StoryMapArtifactEditor } from "./StoryMapArtifactEditor"
import { usePlanningArtifactAmendment } from "../state/usePlanningArtifactAmendment"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

export default function StoryMapStageView() {
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
    activeRun?.read_model.artifact_refs.story_map ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "story_map",
      ),
  )
  const draft = usePhase32ArtifactDraft(
    runId,
    "story_map",
    activeRun?.read_model.updated_at ?? "",
    artifactAvailable,
  )
  const amendment = usePlanningArtifactAmendment("story_map", draft.current)
  const amendmentActive = amendment.flow.phase !== "idle"
  const editMode = useArtifactEditMode(
    Boolean(
      draft.current?.editable || amendment.flow.canStart || amendmentActive,
    ),
    draft.current?.artifact_ref ?? "",
  )
  const workingPayload = amendment.flow.payload ?? draft.payload
  const parsed = useMemo(
    () => parsePhase32StoryMap(workingPayload),
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
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在同步故事地图"
        detail="读取锚点顺序、作者草稿与当前决策"
      />
    )
  }
  if (!activeRun) {
    return (
      <StoryMapEmptyState
        title="Run 尚未就绪"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        actionLabel="返回作品库"
        onAction={() => setRoute("studio")}
      />
    )
  }

  const status = activeRun.read_model.stage_status.story_map ?? "locked"
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
      setActionError(parsed.error || "当前故事地图未通过界面合同校验")
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
        if (nextStageId !== "story_map" && isProductionStageRoute(nextStageId))
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "故事地图决策提交失败",
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
        label="正在生成故事地图"
        detail="候选稿通过结构校验后会在这里进入作者决策"
      />
    ) : (
      <StoryMapEmptyState
        title="故事地图尚未生成"
        detail={
          draft.error ||
          parsed.error ||
          runError ||
          "请先完成上游 Brief 并启动当前阶段。"
        }
        actionLabel="前往运行监控"
        onAction={() => setRoute("run-monitor")}
      />
    )
  }

  const revisionLabel = decision
    ? `Revision ${decision.domain_revision ?? "历史"} · 换稿 ${decision.redraft_used ?? "-"}/${decision.redraft_limit ?? "-"}`
    : "已确认版本"

  return (
    <div className="story-map-page page-in">
      <header className="story-map-toolbar">
        <div className="story-map-toolbar-state">
          {draft.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {draft.current.status === "committed"
              ? "故事地图已定稿"
              : canDecide
                ? "候选稿等待作者决策"
                : "历史决策只读"}
          </span>
          <small>{draftStatusLabel(draft.status)}</small>
        </div>
        <div className="story-map-actions">
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
              {actionState === "accepting" ? "正在定稿…" : "确认故事地图"}
            </button>
          ) : amendment.flow.phase === "idle" &&
            activeTarget &&
            activeTarget.stage_id !== "story_map" &&
            draft.current.status === "committed" ? (
            <button
              type="button"
              className="btn btn-primary text-xs"
              onClick={() => {
                if (isProductionStageRoute(activeTarget.stage_id))
                  setRoute(activeTarget.stage_id)
              }}
            >
              进入{activeTarget.label} <Play size={12} />
            </button>
          ) : null}
        </div>
      </header>

      {(actionError || draft.error || parsed.error || runError) && (
        <div className="story-map-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{actionError || draft.error || parsed.error || runError}</span>
        </div>
      )}

      <StoryMapArtifactEditor
        artifact={parsed.artifact}
        artifactRef={draft.current.artifact_ref}
        editable={editMode.editing}
        revisionLabel={revisionLabel}
        onChange={changeArtifact}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          id="phase32-story-map-dialog"
          kind={dialog}
          busy={busy}
          direction={direction}
          error={actionError}
          regenerateDescription="只调整故事锚点的推进方式；稳定引用、冻结规模与上游 Brief 保持不变。"
          placeholder="例如：删去重复的信息揭示，让第二个锚点由人物选择直接造成更大的后果。"
          suggestions={[
            "合并重复推进的锚点，让每一步都改变局面。",
            "强化人物选择与后果之间的可见联系。",
            "让结尾状态更明确地兑现开场提出的故事问题。",
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

function StoryMapEmptyState({
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
    <div className="story-map-empty page-in">
      <GitBranch size={22} />
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
