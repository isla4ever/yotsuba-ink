import { useState } from "react"
import "../../../styles/phase32-script-delivery-receipt.css"
import {
  Check,
  Copy,
  Fingerprint,
  HardDriveDownload,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react"
import {
  deliveryFormatLabel,
  formatDeliveryBytes,
  type ScriptDeliveryReceipt as Receipt,
} from "../lib/phase32ScriptDelivery"

type Props = {
  artifactDigest: string
  downloadState: "idle" | "downloading" | "downloaded" | "error"
  receipt: Receipt
  sceneCount: number
}

export function ScriptDeliveryReceipt({
  artifactDigest,
  downloadState,
  receipt,
  sceneCount,
}: Props) {
  const [copied, setCopied] = useState(false)

  const copyDigest = async () => {
    await navigator.clipboard?.writeText(receipt.sha256)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  return (
    <aside className="script-delivery-receipt" aria-label="交付回执">
      <header>
        <div>
          <ShieldCheck size={14} />
          <span>交付回执</span>
        </div>
        <strong>VERIFIED</strong>
      </header>

      <div className="script-delivery-receipt-body">
        <section className="script-delivery-seal">
          <span>
            <Fingerprint size={18} />
          </span>
          <div>
            <small>冻结制品</small>
            <strong>{deliveryFormatLabel(receipt.format)}</strong>
            <p>由 committed Scene 版本确定性物化</p>
          </div>
        </section>

        <dl className="script-delivery-receipt-grid">
          <div>
            <dt>Scene</dt>
            <dd>
              {sceneCount} / {sceneCount}
            </dd>
          </div>
          <div>
            <dt>文件大小</dt>
            <dd>{formatDeliveryBytes(receipt.size_bytes)}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{formatReceiptTime(receipt.created_at)}</dd>
          </div>
          <div>
            <dt>下载状态</dt>
            <dd className={`is-${downloadState}`}>
              {downloadStateLabel(downloadState)}
            </dd>
          </div>
        </dl>

        <section className="script-delivery-hash">
          <header>
            <span>SHA-256</span>
            <button
              aria-label="复制文件哈希"
              onClick={() => void copyDigest()}
              title="复制文件哈希"
              type="button"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
            </button>
          </header>
          <code>{receipt.sha256}</code>
        </section>

        <section className="script-delivery-source">
          <div>
            <span>Artifact digest</span>
            <code>{shortDigest(artifactDigest)}</code>
          </div>
          <div>
            <span>Export ref</span>
            <code>{shortRef(receipt.artifact_ref)}</code>
          </div>
        </section>
      </div>

      <footer>
        <LockKeyhole size={12} />
        <span>正文、顺序与格式均已冻结；下载不会触发重新生成。</span>
      </footer>
    </aside>
  )
}

function downloadStateLabel(state: Props["downloadState"]) {
  if (state === "downloading") return "校验中"
  if (state === "downloaded") return "已下载"
  if (state === "error") return "下载失败"
  return "就绪"
}

function formatReceiptTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date)
}

function shortDigest(value: string) {
  return value ? `${value.slice(0, 12)}…${value.slice(-8)}` : "-"
}

function shortRef(value: string) {
  return value.length > 34 ? `${value.slice(0, 18)}…${value.slice(-10)}` : value
}
