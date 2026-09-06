import { useEffect, useState } from "react"
import "../../../styles/phase32-book-delivery-shell.css"
import "../../../styles/phase32-book-delivery-manifest.css"
import "../../../styles/phase32-book-delivery-receipt.css"
import {
  AlertTriangle,
  ArrowLeft,
  BookCheck,
  CheckCircle2,
  RefreshCw,
} from "lucide-react"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"
import type { BookDeliveryReceipt } from "../lib/phase32BookDelivery"
import { downloadBookDelivery } from "../services/bookDeliveryApi"
import { useApp } from "../state/PipelineAppProvider"
import { usePhase32BookDelivery } from "../state/usePhase32BookDelivery"
import {
  BookDeliveryWorkbench,
  type BookDeliveryDownloadState,
} from "./BookDeliveryWorkbench"

export default function BookDeliveryStageView() {
  const { activeProject, activeRun, runError, runLoading, setRoute } = useApp()
  const runId = activeRun?.definition.run_id ?? ""
  const delivery = usePhase32BookDelivery(
    runId,
    activeRun?.read_model.updated_at ?? "",
    Boolean(
      activeProject && activeProject.creationRouteId !== "screenplay_sample",
    ),
  )
  const [selectedExportId, setSelectedExportId] = useState("")
  const [downloadStates, setDownloadStates] =
    useState<Record<string, BookDeliveryDownloadState>>({})
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
        detail="核验正式封面、正文版本清单、格式文件与 SHA-256 回执"
        label="正在装载成书交付"
        phase={loading.exiting ? "exit" : "enter"}
        variant="panel"
      />
    )
  }
  if (activeProject.creationRouteId === "screenplay_sample") {
    return (
      <BookDeliveryEmptyState
        actionLabel="返回当前阶段"
        detail="剧本样片使用 Fountain、PDF 与 Markdown 的独立交付工作台。"
        onAction={() => setRoute("script")}
        title="当前页面仅用于小说成书"
      />
    )
  }
  const dependencyDeferred = delivery.dependencyStatus === "deferred"
  if (
    !activeRun ||
    !delivery.artifact ||
    !delivery.envelope ||
    !selectedReceipt
  ) {
    return (
      <BookDeliveryEmptyState
        actionLabel="返回封面阶段"
        detail={
          delivery.error ||
          runError ||
          "请先确认正式封面；系统会在 Export 提交时确定性物化成书文件。"
        }
        onAction={() => setRoute("cover")}
        title={
          dependencyDeferred ? "正文已完成，成书交付暂缓" : "成书交付尚未就绪"
        }
        deferred={dependencyDeferred}
      />
    )
  }

  const handleDownload = async (receipt: BookDeliveryReceipt) => {
    if (downloadStates[receipt.export_id] === "downloading") return
    setDownloadStates((current) => ({
      ...current,
      [receipt.export_id]: "downloading",
    }))
    setDownloadError("")
    try {
      await downloadBookDelivery(runId, receipt)
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
        reason instanceof Error ? reason.message : "成书文件下载失败",
      )
    }
  }

  return (
    <div className="book-delivery-page page-in">
      <header className="book-delivery-toolbar">
        <div className="book-delivery-toolbar-state">
          <CheckCircle2 size={13} />
          <span>小说交付已冻结</span>
          <small>
            {delivery.manifest.length} UNITS · {receipts.length} FILES
          </small>
        </div>
        <div className="book-delivery-toolbar-actions">
          <button
            className="btn btn-ghost text-xs"
            onClick={() => setRoute("cover")}
            type="button"
          >
            <ArrowLeft size={13} /> 返回正式封面
          </button>
          <button
            aria-label="重新核验成书文件"
            className="btn btn-icon btn-ghost"
            onClick={delivery.reload}
            title="重新核验成书文件"
            type="button"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </header>

      {delivery.error || downloadError ? (
        <div className="book-delivery-alert" role="alert">
          <AlertTriangle size={13} />
          <span>{delivery.error || downloadError}</span>
        </div>
      ) : null}

      <BookDeliveryWorkbench
        artifact={delivery.artifact}
        artifactDigest={delivery.artifactDigest}
        downloadStates={downloadStates}
        manifest={delivery.manifest}
        onDownload={(receipt) => void handleDownload(receipt)}
        onSelectReceipt={(receipt) => setSelectedExportId(receipt.export_id)}
        receipts={receipts}
        runId={runId}
        selectedReceipt={selectedReceipt}
      />
    </div>
  )
}

function BookDeliveryEmptyState({
  actionLabel,
  detail,
  deferred = false,
  onAction,
  title,
}: {
  actionLabel: string
  detail: string
  deferred?: boolean
  onAction: () => void
  title: string
}) {
  return (
    <div
      className={`book-delivery-empty page-in${deferred ? " is-deferred" : ""}`}
    >
      {deferred ? <AlertTriangle size={22} /> : <BookCheck size={22} />}
      {deferred ? (
        <span className="book-delivery-empty-kicker">
          DEPENDENCY DEFERRED · IMAGE ACCEPTANCE
        </span>
      ) : null}
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
