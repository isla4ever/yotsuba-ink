import {
  CheckCircle2,
  FileCheck2,
  Fingerprint,
  HardDriveDownload,
  ShieldCheck,
} from "lucide-react"
import {
  bookDeliveryFormatLabel,
  formatBookDeliveryBytes,
  type BookDeliveryReceipt as Receipt,
} from "../lib/phase32BookDelivery"
import type { BookDeliveryDownloadState } from "./BookDeliveryWorkbench"

type Props = {
  artifactDigest: string
  downloadState: BookDeliveryDownloadState
  receipt: Receipt
}

export function BookDeliveryReceipt({
  artifactDigest,
  downloadState,
  receipt,
}: Props) {
  return (
    <aside className="book-delivery-receipt" aria-label="成书交付回执">
      <header>
        <ShieldCheck size={13} />
        <div>
          <span>交付回执</span>
          <small>IMMUTABLE FILE</small>
        </div>
      </header>

      <section className="book-delivery-receipt-state">
        <CheckCircle2 size={17} />
        <div>
          <small>文件状态</small>
          <strong>{downloadStateLabel(downloadState)}</strong>
        </div>
      </section>

      <section>
        <span>当前文件</span>
        <dl>
          <ReceiptRow
            label="格式"
            value={bookDeliveryFormatLabel(receipt.format)}
          />
          <ReceiptRow label="文件名" value={receipt.filename} />
          <ReceiptRow
            label="大小"
            value={formatBookDeliveryBytes(receipt.size_bytes)}
          />
          <ReceiptRow
            label="章节"
            value={`${receipt.chapter_manifest.length}`}
          />
          <ReceiptRow label="封面" value={shortDigest(receipt.cover_sha256)} />
        </dl>
      </section>

      <section>
        <span>内容寻址</span>
        <div className="book-delivery-hash">
          <FileCheck2 size={12} />
          <code>{receipt.sha256}</code>
        </div>
      </section>

      <section>
        <span>来源身份</span>
        <div className="book-delivery-receipt-source">
          <Fingerprint size={12} />
          <div>
            <small>Artifact digest</small>
            <code>{shortDigest(artifactDigest)}</code>
          </div>
        </div>
        <div className="book-delivery-receipt-source">
          <HardDriveDownload size={12} />
          <div>
            <small>Export receipt</small>
            <code>{shortRef(receipt.export_id)}</code>
          </div>
        </div>
      </section>

      <footer>
        下载前后都按 SHA-256 核验；页面不会重新生成正文、封面或文件。
      </footer>
    </aside>
  )
}

type ReceiptRowProps = {
  label: string
  value: string
}

function ReceiptRow({ label, value }: ReceiptRowProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function downloadStateLabel(state: BookDeliveryDownloadState) {
  if (state === "downloading") return "正在校验下载"
  if (state === "downloaded") return "已下载并核验"
  if (state === "error") return "下载核验失败"
  return "文件就绪"
}

function shortDigest(value: string) {
  return value ? `${value.slice(0, 9)}…${value.slice(-7)}` : "-"
}

function shortRef(value: string) {
  return value.length > 26 ? `${value.slice(0, 15)}…${value.slice(-8)}` : value
}
