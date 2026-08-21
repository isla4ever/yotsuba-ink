import { useMemo, useState } from "react"
import {
  AlertTriangle,
  ChevronLeft,
  CircleStop,
  Lock,
  RefreshCw,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import type { ExportArtifact } from "@/features/pipeline/contracts/delivery"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import {
  parseCoverArtifact,
  parseExportArtifact,
} from "@/features/pipeline/lib/deliveryArtifact"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import {
  DeliveryDecisionDialog,
  DeliveryEmpty,
  DeliveryStageBar,
  deliveryDraftStatusLabel,
} from "@/features/pipeline/running/DeliveryStageShell"
import { ExportArtifactWorkbench } from "@/features/pipeline/running/ExportArtifactWorkbench"
import { resolveRunDecision } from "@/features/pipeline/services/runApi"
import { useCoverAssets } from "@/features/pipeline/state/useCoverAssets"
import { useExportDelivery } from "@/features/pipeline/state/useExportDelivery"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"

type DialogKind = "regenerate" | "cancel" | null

export default function ExportStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runCandidateArtifacts,
    runChapters,
    runLoading,
    setRoute,
  } = useApp()
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "export"),
    [activeRun],
  )
  const committed = runArtifacts.export
  const candidate = runCandidateArtifacts.export
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const draft = useStageArtifactDraft(runId, decision, source)
  const parsed = useMemo(
    () => parseExportArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const cover = useMemo(
    () => parseCoverArtifact(runArtifacts.cover?.payload),
    [runArtifacts.cover],
  )
  const coverAssets = useCoverAssets(runId, Boolean(activeRun))
  const artifact = parsed.artifact
  const delivery = useExportDelivery(
    runId,
    artifact,
    Boolean(committed && !decision),
    committed?.signature ?? "",
  )
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] =
    useState<"idle" | "accepting" | "regenerating" | "cancelling">("idle")
  const [actionError, setActionError] = useState("")
  const stageStatus = activeRun?.read_model.stage_status.export ?? "locked"
  const versionRecords = useMemo(
    () => new Map(runChapters.map((record) => [record.version_id, record])),
    [runChapters],
  )
  const versionsReady = Boolean(
    artifact &&
      artifact.chapter_version_ids.every(
        (versionId) =>
          versionRecords.get(versionId)?.artifact.author_status === "accepted",
      ),
  )
  const coverMatches = Boolean(
    artifact &&
      cover.artifact &&
      artifact.cover_asset_id === cover.artifact.selected_asset_id,
  )
  const canAccept = Boolean(
    decision && candidate && artifact && versionsReady && coverMatches,
  )

  const update = (next: ExportArtifact) => {
    if (!decision) return
    draft.change(next as unknown as Record<string, unknown>)
  }

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!activeRun || !decision || actionState !== "idle") return
    if (action === "accept" && !artifact) {
      setActionError(parsed.error || "当前导出稿未通过 Artifact 合同校验")
      return
    }
    if (action === "accept" && (!versionsReady || !coverMatches)) {
      setActionError("导出清单与已接受正文版本或正式封面不一致")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次重建清单的方向")
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
        reason instanceof Error ? reason.message : "导出阶段决策提交失败",
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
        label="正在核对交付清单"
        detail="同步 Export Artifact、章节版本与不可变回执"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <DeliveryEmpty
        stage="export"
        title="当前作品尚未启动创作 Run"
        detail="全部阶段完成后，系统才会生成可确认的交付清单。"
        onBack={() => setRoute("studio")}
      />
    )
  }

  if (generationLoad.visible || !source || !artifact) {
    return (
      <div className="flex-1 flex flex-col page-in">
        <DeliveryStageBar
          stage="export"
          status={stageStatus}
          detail="当前阶段尚无 Export Artifact"
        />
        <div className="flex-1 grid place-items-center p-6">
          {generationLoad.visible ? (
            <BookLoader
              phase={generationLoad.exiting ? "exit" : "enter"}
              variant="compact"
              label="正在编制交付清单"
              detail="系统正在绑定全部已接受章节版本与正式封面"
            />
          ) : (
            <DeliveryEmpty
              stage="export"
              title={
                stageStatus === "locked"
                  ? "导出阶段尚未解锁"
                  : "导出清单尚未就绪"
              }
              detail={
                runArtifactError ||
                (source
                  ? parsed.error || "Export Artifact 暂时无法读取。"
                  : "请先完成正文与封面定稿，再等待 Export Artifact。")
              }
              onBack={() => setRoute("cover")}
            />
          )}
        </div>
      </div>
    )
  }

  const selectedCover = coverAssets.assets.find(
    (item) => item.asset_id === artifact.cover_asset_id,
  )

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <DeliveryStageBar
        stage="export"
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
                <RefreshCw size={12} /> 重建清单
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
              {actionState === "accepting" ? "正在交付…" : "确认并物化"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-secondary text-xs"
            onClick={() => setRoute("cover")}
          >
            <ChevronLeft size={13} /> 查看封面
          </button>
        )}
      </DeliveryStageBar>

      {(actionError || draft.error || delivery.error || runArtifactError) && (
        <div className="mx-4 md:mx-6 mt-3 banner-warning" role="alert">
          <AlertTriangle size={13} />
          {actionError || draft.error || delivery.error || runArtifactError}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <ExportArtifactWorkbench
          artifact={artifact}
          committed={Boolean(committed && !decision)}
          coverMatches={coverMatches}
          decision={Boolean(decision)}
          delivery={delivery}
          onChange={update}
          parserReady={Boolean(parsed.artifact)}
          runId={runId}
          selectedCover={selectedCover}
          versionRecords={versionRecords}
          versionsReady={versionsReady}
        />
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
      <DeliveryDecisionDialog title="重建导出清单" onClose={onClose}>
        <p className="text-xs text-fog leading-6">
          Export 不调用
          Provider；系统只会按当前已接受章节、正式封面和冻结元数据重新编制清单。
        </p>
        <label className="block mt-4">
          <span className="text-xs text-ash block mb-1.5">重建说明</span>
          <textarea
            className="input"
            rows={3}
            value={direction}
            onChange={(event) => onDirection(event.target.value)}
            placeholder="例如：改为 Markdown 格式并补充版本说明。"
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
            <RefreshCw size={12} />
            {actionState === "regenerating" ? "正在提交…" : "重建清单"}
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
          <span>取消后不会生成交付包；已提交的上游 Artifact 仍保留。</span>
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
