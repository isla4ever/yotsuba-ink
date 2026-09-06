import { useEffect, useState } from "react"
import "../../../styles/phase32-script-delivery.css"
import { AlertTriangle, ArrowLeft, CheckCircle2, RefreshCw } from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import type { ScriptDeliveryReceipt } from "../lib/phase32ScriptDelivery"
import { downloadScriptDelivery } from "../services/scriptDeliveryApi"
import { useApp } from "../state/PipelineAppProvider"
import { usePhase32ScriptDelivery } from "../state/usePhase32ScriptDelivery"
import {
  ScriptDeliveryWorkbench,
  type DeliveryDownloadState,
} from "./ScriptDeliveryWorkbench"

export default function ScriptDeliveryStageView() {
  const { activeProject, activeRun, runError, runLoading, setRoute } = useApp()
  const runId = activeRun?.definition.run_id ?? ""
  const authorityRevision = activeRun?.read_model.updated_at ?? ""
  const delivery = usePhase32ScriptDelivery(
    runId,
    authorityRevision,
    activeProject?.creationRouteId === "screenplay_sample",
  )
  const [selectedExportId, setSelectedExportId] = useState("")
  const [downloadStates, setDownloadStates] =
    useState<Record<string, DeliveryDownloadState>>({})
  const [downloadError, setDownloadError] = useState("")
  const loading = useLoadingPresence(runLoading || delivery.loading)

  const receipts = delivery.envelope?.receipts ?? []
  const selectedReceipt =
    receipts.find((receipt) => receipt.export_id === selectedExportId) ??
    receipts[0]

  useEffect(() => {
    if (
      receipts.length &&
      !receipts.some((receipt) => receipt.export_id === selectedExportId)
    )
      setSelectedExportId(receipts[0].export_id)
  }, [receipts, selectedExportId])

  if (!activeProject) return null
  if (loading.visible) {
    return (
      <BookLoader
        detail="核验冻结 Scene、版本来源、格式文件与 SHA-256 回执"
        label="正在装载剧本交付"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (activeProject.creationRouteId !== "screenplay_sample") {
    return (
      <DeliveryEmptyState
        actionLabel="返回当前阶段"
        detail="短中篇与长篇的专业成书交付将在各自 Cover 合同完成后独立迁移。"
        onAction={() => setRoute("studio")}
        title="当前页面仅用于剧本交付"
      />
    )
  }
  if (
    !activeRun ||
    !delivery.artifact ||
    !delivery.envelope ||
    !selectedReceipt
  ) {
    return (
      <DeliveryEmptyState
        actionLabel="返回剧本正文"
        detail={
          delivery.error ||
          runError ||
          "请先确认全部 Scene，系统会在 Export 提交时物化冻结文件。"
        }
        onAction={() => setRoute("script")}
        title="剧本交付尚未就绪"
      />
    )
  }

  const handleDownload = async (receipt: ScriptDeliveryReceipt) => {
    if (downloadStates[receipt.export_id] === "downloading") return
    setDownloadStates((current) => ({
      ...current,
      [receipt.export_id]: "downloading",
    }))
    setDownloadError("")
    try {
      await downloadScriptDelivery(runId, receipt)
      setDownloadStates((current) => ({
        ...current,
        [receipt.export_id]: "downloaded",
      }))
    } catch (reason) {
      setDownloadStates((current) => ({
        ...current,
        [receipt.export_id]: "error",
      }))
      setDownloadError(
        reason instanceof Error ? reason.message : "剧本文件下载失败",
      )
    }
  }

  return (
    <div className="script-delivery-page page-in">
      <header className="script-delivery-toolbar">
        <div className="script-delivery-toolbar-state">
          <CheckCircle2 size={13} />
          <span>剧本交付已冻结</span>
          <small>
            {delivery.manifest.length} SCENES · {receipts.length} FILES
          </small>
        </div>
        <div className="script-delivery-toolbar-actions">
          <button
            className="btn btn-ghost text-xs"
            onClick={() => setRoute("script")}
            type="button"
          >
            <ArrowLeft size={13} /> 返回剧本正文
          </button>
          <button
            aria-label="重新核验交付文件"
            className="btn btn-icon btn-ghost"
            onClick={delivery.reload}
            title="重新核验交付文件"
            type="button"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </header>

      {delivery.error || downloadError ? (
        <div className="script-delivery-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{delivery.error || downloadError}</span>
        </div>
      ) : null}

      <ScriptDeliveryWorkbench
        artifact={delivery.artifact}
        artifactDigest={delivery.artifactDigest}
        downloadStates={downloadStates}
        manifest={delivery.manifest}
        onDownload={(receipt) => void handleDownload(receipt)}
        onSelectReceipt={(receipt) => setSelectedExportId(receipt.export_id)}
        receipts={receipts}
        selectedReceipt={selectedReceipt}
      />
    </div>
  )
}

function DeliveryEmptyState({
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
    <div className="script-delivery-empty page-in">
      <CheckCircle2 size={20} />
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
