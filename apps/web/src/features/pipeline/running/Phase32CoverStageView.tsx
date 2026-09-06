import { useState } from "react"
import "../../../styles/phase32-cover-shell.css"
import "../../../styles/phase32-cover-assets.css"
import "../../../styles/phase32-cover-inspector.css"
import {
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  FilePenLine,
  Image,
  Lock,
  Play,
  Sparkles,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import { isProductionStageRoute } from "../lib/routes"
import { resolvePhase32RunDecision } from "../services/runApi"
import { useApp } from "../state/PipelineAppProvider"
import { usePhase32Cover } from "../state/usePhase32Cover"
import {
  Phase32StageDecisionDialog,
  type Phase32DecisionDialogKind,
} from "./Phase32StageDecisionDialog"
import { Phase32CoverWorkbench } from "./Phase32CoverWorkbench"

type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

export default function Phase32CoverStageView() {
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
    activeRun?.read_model.artifact_refs.cover ||
      activeRun?.read_model.pending_decisions.some(
        (decision) => decision.stage_id === "cover",
      ),
  )
  const cover = usePhase32Cover(
    runId,
    activeRun?.read_model.updated_at ?? "",
    artifactAvailable,
  )
  const loading = useLoadingPresence(
    runLoading || cover.loading || cover.assetStatus === "loading",
  )

  if (!activeProject) return null
  if (loading.visible) {
    return (
      <BookLoader
        detail="读取视觉 Brief、不可变图片资产与当前作者选择"
        label="正在同步封面审阅台"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (!activeRun) {
    return (
      <CoverEmptyState
        actionLabel="返回作品库"
        detail={runError || "作品已创建，但当前 Run 还没有可读取的权威状态。"}
        onAction={() => setRoute("studio")}
        title="Run 尚未就绪"
      />
    )
  }

  const status = activeRun.read_model.stage_status.cover ?? "locked"
  const decision = cover.current?.pending_decision ?? null
  const imageDeferred =
    cover.artifact?.image_acceptance_status === "image_deferred"
  const canDecide = Boolean(
    cover.current?.editable && decision?.domain_revision !== null,
  )
  const busy = actionState !== "idle"
  const activeTarget = activeRun.read_model.stage_manifest.find(
    (item) => item.stage_id === activeRun.read_model.active_stage_id,
  )

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!decision || decision.domain_revision === null || busy) return
    if (action === "accept") {
      if (!imageDeferred && !cover.artifact?.selected_asset_ref) {
        setActionError("请先从左侧候选中选择一张真实图片作为正式封面")
        return
      }
      if (!imageDeferred && (cover.artifactError || cover.assetError)) {
        setActionError(cover.artifactError || cover.assetError)
        return
      }
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次封面定向换稿要求")
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
      const draftRef = action === "accept" ? await cover.flush() : ""
      const resolved = await resolvePhase32RunDecision(runId, {
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
      if (action === "accept") {
        const nextStageId = resolved.read_model.active_stage_id
        if (nextStageId !== "cover" && isProductionStageRoute(nextStageId))
          setRoute(nextStageId)
      }
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "封面决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  if (cover.status === "empty" || !cover.current || !cover.artifact) {
    return status === "running" ? (
      <BookLoader
        detail="文本提案完成后，系统会逐张生成并核验真实图片资产"
        label="正在生成封面候选"
        variant="compact"
      />
    ) : (
      <CoverEmptyState
        actionLabel="前往运行监控"
        detail={
          cover.error ||
          cover.artifactError ||
          runError ||
          "请先完成全部正文单元，封面阶段随后会自动进入生成。"
        }
        onAction={() => setRoute("run-monitor")}
        title="封面尚未生成"
      />
    )
  }

  const revisionLabel = decision
    ? `Revision ${decision.domain_revision ?? "历史"} · 换稿 ${decision.redraft_used ?? "-"}/${decision.redraft_limit ?? "-"}`
    : "已确认不可变版本"

  return (
    <div className="phase32-cover-page page-in">
      <header className="phase32-cover-toolbar">
        <div className="phase32-cover-toolbar-state">
          {cover.current.status === "committed" ? (
            <CheckCircle2 size={13} />
          ) : (
            <FilePenLine size={13} />
          )}
          <span>
            {cover.current.status === "committed"
              ? imageDeferred
                ? "CoverBrief 已冻结 · 图片验收暂缓"
                : "正式封面已冻结"
              : cover.artifact.selected_asset_ref
                ? "正式候选等待定稿"
                : imageDeferred
                  ? "CoverBrief 等待确认"
                  : "请选择正式封面"}
          </span>
          <small>{draftStatusLabel(cover.status)}</small>
        </div>
        <div className="phase32-cover-actions">
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
                busy ||
                (!imageDeferred && !cover.artifact.selected_asset_ref) ||
                Boolean(cover.artifactError || cover.assetError)
              }
              onClick={() => void submitDecision("accept")}
              type="button"
            >
              <Lock size={12} />
              {actionState === "accepting"
                ? "正在提交…"
                : imageDeferred
                  ? "确认 CoverBrief"
                  : "确认正式封面"}
            </button>
          ) : activeTarget?.stage_id === "export" &&
            cover.current.status === "committed" ? (
            <button
              className="btn btn-primary text-xs"
              onClick={() => setRoute("export")}
              type="button"
            >
              进入成书交付 <Play size={12} />
            </button>
          ) : null}
        </div>
      </header>

      {(actionError ||
        cover.error ||
        cover.artifactError ||
        cover.assetError ||
        runError) && (
        <div className="phase32-cover-alert" role="alert">
          <AlertTriangle size={13} />
          <span>
            {actionError ||
              cover.error ||
              cover.artifactError ||
              cover.assetError ||
              runError}
          </span>
        </div>
      )}

      <Phase32CoverWorkbench
        artifact={cover.artifact}
        artifactRef={cover.current.artifact_ref}
        assets={cover.assets}
        canSelect={canDecide && !busy}
        generationAttempt={cover.generationAttempt}
        projectTitle={activeProject.title}
        revisionLabel={revisionLabel}
        runId={runId}
        onSelect={(assetRef) => {
          setActionError("")
          cover.selectAsset(assetRef)
        }}
      />

      {dialog ? (
        <Phase32StageDecisionDialog
          busy={busy}
          direction={direction}
          error={actionError}
          id="phase32-cover-dialog"
          kind={dialog}
          placeholder="例如：保留档案感，但减少人物面部特写，扩大标题安全区，并提高冷暖层次。"
          regenerateDescription="只重做当前封面的视觉提案与真实图片资产；已接受正文、标题与导出配置保持不变。"
          suggestions={[
            "增强标题安全区，减少视觉元素彼此争抢。",
            "保留核心意象，降低人物写实感与模板化构图。",
            "提高明暗层次，让缩略图状态仍能辨识主题。",
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

function CoverEmptyState({
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
    <div className="phase32-cover-empty page-in">
      <Image size={22} />
      <h1>{title}</h1>
      <p>{detail}</p>
      <button
        className="btn btn-secondary text-xs"
        onClick={onAction}
        type="button"
      >
        {actionLabel}
      </button>
    </div>
  )
}

function draftStatusLabel(status: string) {
  if (status === "dirty") return "选择待保存"
  if (status === "saving") return "正在保存"
  if (status === "saved") return "选择已保存"
  if (status === "readonly") return "只读"
  if (status === "error") return "保存失败"
  return "已同步"
}
