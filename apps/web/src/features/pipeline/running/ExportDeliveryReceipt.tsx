import {
  Download,
  FileArchive,
  Package,
  RefreshCw,
  ShieldCheck,
} from "lucide-react"
import type { useExportDelivery } from "../state/useExportDelivery"

export function ExportDeliveryReceipt({
  committed,
  delivery,
}: {
  committed: boolean
  delivery: ReturnType<typeof useExportDelivery>
}) {
  const receipt = delivery.receipt
  const busy =
    delivery.status === "loading" || delivery.status === "downloading"
  return (
    <section
      className="border border-hairline rounded-lg bg-surface overflow-hidden"
      aria-live="polite"
    >
      <header className="px-4 py-3 border-b border-hairline flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink flex items-center gap-2">
          {receipt ? (
            <ShieldCheck size={13} className="text-mint" />
          ) : (
            <Package size={13} className="text-fog" />
          )}
          不可变交付回执
        </span>
        <span className={`badge ${receipt ? "badge-mint" : "badge-ash"}`}>
          {receipt ? "可下载" : deliveryStatusLabel(delivery.status, committed)}
        </span>
      </header>
      {receipt ? (
        <div className="p-4">
          <strong className="text-sm text-ink block break-all">
            {receipt.filename}
          </strong>
          <dl className="mt-4 space-y-2.5">
            <ReceiptFact label="大小" value={formatBytes(receipt.size_bytes)} />
            <ReceiptFact label="格式" value={receipt.format.toUpperCase()} />
            <ReceiptFact
              label="物化时间"
              value={formatDateTime(receipt.created_at)}
            />
            <ReceiptFact label="SHA-256" value={receipt.sha256} mono />
          </dl>
          <button
            type="button"
            className="btn btn-primary w-full justify-center mt-4"
            disabled={busy}
            onClick={() => void delivery.download()}
          >
            <Download size={13} />
            {delivery.status === "downloading" ? "校验文件中…" : "校验并下载"}
          </button>
          <p className="text-[10px] text-fog leading-5 mt-2">
            下载前会核对响应摘要、Receipt、文件大小与本地 SHA-256。
          </p>
        </div>
      ) : (
        <div className="p-5 text-center">
          {busy ? (
            <RefreshCw
              size={22}
              className="text-action animate-spin mx-auto mb-3"
            />
          ) : (
            <FileArchive size={22} className="text-fog mx-auto mb-3" />
          )}
          <p className="text-xs text-ash leading-6">
            {deliveryStatusHint(delivery.status, committed)}
          </p>
        </div>
      )}
    </section>
  )
}

function ReceiptFact({
  label,
  mono,
  value,
}: {
  label: string
  mono?: boolean
  value: string
}) {
  return (
    <div>
      <dt className="text-[10px] text-fog">{label}</dt>
      <dd
        className={`text-xs text-ash mt-0.5 break-all ${mono ? "font-mono" : ""}`}
      >
        {value}
      </dd>
    </div>
  )
}

function deliveryStatusLabel(
  status: ReturnType<typeof useExportDelivery>["status"],
  committed: boolean,
) {
  if (!committed) return "等待确认"
  if (status === "loading") return "读取中"
  if (status === "missing") return "尚未物化"
  if (status === "error") return "回执异常"
  return "等待回执"
}

function deliveryStatusHint(
  status: ReturnType<typeof useExportDelivery>["status"],
  committed: boolean,
) {
  if (!committed)
    return "确认当前 Export Artifact 后，系统会物化不可变交付文件。"
  if (status === "loading")
    return "正在读取与当前 Artifact 完全匹配的交付回执。"
  if (status === "missing")
    return "当前正式 Artifact 尚未找到匹配回执，不能提供下载。"
  if (status === "error")
    return "交付回执暂时不可用；错误信息已显示在页面顶部。"
  return "交付回执将在 Export Artifact 正式提交后出现。"
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}
