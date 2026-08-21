import { useMemo, useState } from "react"
import {
  AlertTriangle,
  CircleStop,
  ChevronRight,
  Image,
  Lock,
  Sparkles,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { parseCoverArtifact } from "@/features/pipeline/lib/deliveryArtifact"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import { CoverAssetGallery } from "@/features/pipeline/running/CoverAssetGallery"
import { CoverBriefPanel } from "@/features/pipeline/running/CoverBriefPanel"
import {
  DeliveryDecisionDialog,
  DeliveryEmpty,
  DeliveryStageBar,
  deliveryDraftStatusLabel,
} from "@/features/pipeline/running/DeliveryStageShell"
import { resolveRunDecision } from "@/features/pipeline/services/runApi"
import { useCoverAssets } from "@/features/pipeline/state/useCoverAssets"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"

type DialogKind = "regenerate" | "cancel" | null

export default function CoverStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runCandidateArtifacts,
    runLoading,
    setRoute,
  } = useApp()
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "cover"),
    [activeRun],
  )
  const committed = runArtifacts.cover
  const candidate = runCandidateArtifacts.cover
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const includeCoverImage =
    activeRun?.definition.export_preferences.include_cover_image ?? false
  const draft = useStageArtifactDraft(runId, decision, source)
  const parsed = useMemo(
    () => parseCoverArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const assetState = useCoverAssets(runId, Boolean(activeRun))
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] =
    useState<"idle" | "accepting" | "regenerating" | "cancelling">("idle")
  const [actionError, setActionError] = useState("")
  const stageStatus = activeRun?.read_model.stage_status.cover ?? "locked"
  const artifact = parsed.artifact
  const selectedAsset = artifact
    ? assetState.assets.find(
        (item) => item.asset_id === artifact.selected_asset_id,
      )
    : undefined
  const canAccept = Boolean(
    decision && candidate && artifact && (!includeCoverImage || selectedAsset),
  )

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!activeRun || !decision || actionState !== "idle") return
    if (action === "accept" && !artifact) {
      setActionError(parsed.error || "当前封面稿未通过 Artifact 合同校验")
      return
    }
    if (action === "accept" && includeCoverImage && !selectedAsset) {
      setActionError("请先从本次生成的真实候选资产中选择正式封面")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次换稿方向")
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
      await resolveRunDecision(
        runId,
        decision.decisionId,
        action,
        decision.domainRevision,
        action === "accept"
          ? artifact as unknown as Record<string, unknown>
          : undefined,
        action === "regenerate" ? direction : undefined,
      )
      setDialog(null)
      setDirection("")
      await refreshRun()
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "封面阶段决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)
  const generationLoad = useLoadingPresence(
    (!source || !artifact) && stageStatus === "running",
  )

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在读取封面工作台"
        detail="同步 Cover Artifact 与不可变图片资产"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <DeliveryEmpty
        stage="cover"
        title="当前作品尚未启动创作 Run"
        detail="正文全部定稿后，系统才会生成封面视觉 Brief。"
        onBack={() => setRoute("studio")}
      />
    )
  }

  if (generationLoad.visible || !source || !artifact) {
    return (
      <div className="flex-1 flex flex-col page-in">
        <DeliveryStageBar
          stage="cover"
          status={stageStatus}
          detail="当前阶段尚无 Cover Artifact"
        />
        <div className="flex-1 grid place-items-center p-6">
          {generationLoad.visible ? (
            <BookLoader
              phase={generationLoad.exiting ? "exit" : "enter"}
              variant="compact"
              label="正在生成封面 Brief"
              detail={
                includeCoverImage
                  ? "视觉合同通过后将读取本次真实候选资产"
                  : "本次 Run 仅生成视觉 Brief，不调用图片 Provider"
              }
            />
          ) : (
            <DeliveryEmpty
              stage="cover"
              title={
                stageStatus === "locked"
                  ? "封面阶段尚未解锁"
                  : "封面产物尚未就绪"
              }
              detail={
                runArtifactError ||
                (source
                  ? parsed.error || "Cover Artifact 暂时无法读取。"
                  : "请先完成全部正文定稿，再等待 Cover Artifact。")
              }
              onBack={() => setRoute("text")}
            />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <DeliveryStageBar
        stage="cover"
        status={decision ? "awaiting_decision" : "completed"}
        detail={
          decision
            ? `候选稿 ${candidate?.artifact_id ?? ""} · ${deliveryDraftStatusLabel(draft.status)}`
            : `正式 Artifact ${committed?.artifact_id ?? ""}`
        }
      >
        {decision ? (
          <>
            {decision.allowedActions.includes("regenerate") && (
              <button
                type="button"
                className="btn btn-secondary text-xs"
                onClick={() => setDialog("regenerate")}
              >
                <Sparkles size={12} /> 定向换稿
              </button>
            )}
            {decision.allowedActions.includes("cancel") && (
              <button
                type="button"
                className="btn btn-ghost text-risk text-xs"
                onClick={() => setDialog("cancel")}
              >
                <CircleStop size={12} /> 取消运行
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary text-xs"
              disabled={!canAccept || actionState !== "idle"}
              onClick={() => void submitDecision("accept")}
            >
              <Lock size={12} />
              {actionState === "accepting" ? "正在定稿…" : "确认封面"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-primary text-xs"
            onClick={() => setRoute("export")}
          >
            查看导出 <ChevronRight size={13} />
          </button>
        )}
      </DeliveryStageBar>

      {(actionError || draft.error || assetState.error || runArtifactError) && (
        <div className="mx-4 md:mx-6 mt-3 banner-warning" role="alert">
          <AlertTriangle size={13} />
          {actionError || draft.error || assetState.error || runArtifactError}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <main className="max-w-6xl mx-auto px-4 md:px-6 py-5 md:py-7">
          <header className="flex flex-col md:flex-row md:items-end gap-3 justify-between mb-5">
            <div>
              <span className="text-[10px] font-mono text-fog uppercase tracking-wider">
                {decision ? "候选稿 · 等待作者决策" : "正式 Artifact · 只读"}
              </span>
              <h1 className="font-serif text-xl font-semibold text-ink mt-1">
                封面视觉合同
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="badge badge-ash">
                {activeRun.definition.cover_asset_binding.model ||
                  "图片模型未绑定"}
              </span>
              <span className="badge badge-action">
                {includeCoverImage
                  ? `${activeRun.definition.cover_asset_binding.candidate_count} 张候选`
                  : "本次不生成图片"}
              </span>
            </div>
          </header>

          <div className="grid grid-cols-1 lg:grid-cols-[minmax(250px,0.82fr)_minmax(0,1.45fr)] gap-5 lg:gap-7">
            <CoverBriefPanel artifact={artifact} />
            <CoverAssetGallery
              artifact={artifact}
              assetState={assetState}
              binding={activeRun.definition.cover_asset_binding}
              editable={Boolean(decision)}
              includeCoverImage={includeCoverImage}
              onSelect={(assetId) =>
                draft.change({ ...artifact, selected_asset_id: assetId })
              }
              runId={runId}
            />
          </div>
        </main>
      </div>

      <DecisionDialogs
        actionState={actionState}
        dialog={dialog}
        direction={direction}
        onClose={() => setDialog(null)}
        onDirection={setDirection}
        onSubmit={submitDecision}
      />
    </div>
  )
}

function DecisionDialogs({
  actionState,
  dialog,
  direction,
  onClose,
  onDirection,
  onSubmit,
}: {
  actionState: string
  dialog: DialogKind
  direction: string
  onClose: () => void
  onDirection: (value: string) => void
  onSubmit: (action: "regenerate" | "cancel") => Promise<void>
}) {
  if (dialog === "regenerate") {
    return (
      <DeliveryDecisionDialog title="定向生成新封面" onClose={onClose}>
        <p className="text-xs text-fog leading-6">
          本操作会重新生成视觉 Brief；启用图片时也会创建新一代不可变候选资产。
        </p>
        <label className="block mt-4">
          <span className="text-xs text-ash block mb-1.5">修订方向</span>
          <textarea
            className="input"
            rows={4}
            value={direction}
            onChange={(event) => onDirection(event.target.value)}
            placeholder="例如：减少人物正面特写，强化 24 小时倒计时与城市急救调度意象。"
          />
        </label>
        <div className="flex gap-2 mt-4">
          <button
            type="button"
            className="btn btn-secondary flex-1"
            onClick={onClose}
          >
            返回
          </button>
          <button
            type="button"
            className="btn btn-primary flex-1"
            disabled={!direction.trim() || actionState !== "idle"}
            onClick={() => void onSubmit("regenerate")}
          >
            <Sparkles size={12} />
            {actionState === "regenerating" ? "正在提交…" : "重新生成"}
          </button>
        </div>
      </DeliveryDecisionDialog>
    )
  }
  if (dialog === "cancel") {
    return (
      <DeliveryDecisionDialog title="取消当前 Run？" onClose={onClose}>
        <div className="banner-risk">
          <AlertTriangle size={13} />
          <span>
            取消后当前 Run 停止推进，已提交 Artifact 与资产仍保留为历史证据。
          </span>
        </div>
        <div className="flex gap-2 mt-4">
          <button
            type="button"
            className="btn btn-secondary flex-1"
            onClick={onClose}
          >
            返回
          </button>
          <button
            type="button"
            className="btn btn-danger flex-1"
            disabled={actionState !== "idle"}
            onClick={() => void onSubmit("cancel")}
          >
            <CircleStop size={12} />
            {actionState === "cancelling" ? "正在取消…" : "确认取消"}
          </button>
        </div>
      </DeliveryDecisionDialog>
    )
  }
  return null
}
