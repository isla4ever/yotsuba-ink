import { useState, type ReactNode } from "react"
import {
  BookCheck,
  BookOpenText,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileArchive,
  FileCode2,
  FileText,
  FileType2,
  Image as ImageIcon,
  Layers3,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react"
import {
  bookDeliveryFormatLabel,
  formatBookDeliveryBytes,
  type BookDeliveryArtifact,
  type BookDeliveryChapterRow,
  type BookDeliveryReceipt as Receipt,
} from "../lib/phase32BookDelivery"
import { BookDeliveryReceipt } from "./BookDeliveryReceipt"

export type BookDeliveryDownloadState = "idle" | "downloading" | "downloaded" | "error"

type Props = {
  artifact: BookDeliveryArtifact
  artifactDigest: string
  downloadStates: Record<string, BookDeliveryDownloadState>
  manifest: BookDeliveryChapterRow[]
  onDownload: (receipt: Receipt) => void
  onSelectReceipt: (receipt: Receipt) => void
  receipts: Receipt[]
  runId: string
  selectedReceipt: Receipt
}

const MANIFEST_PAGE_SIZE = 40

export function BookDeliveryWorkbench({
  artifact,
  artifactDigest,
  downloadStates,
  manifest,
  onDownload,
  onSelectReceipt,
  receipts,
  runId,
  selectedReceipt,
}: Props) {
  const [requestedPage, setRequestedPage] = useState(0)
  const pageCount = Math.max(1, Math.ceil(manifest.length / MANIFEST_PAGE_SIZE))
  const page = Math.min(requestedPage, pageCount - 1)
  const rows = manifest.slice(
    page * MANIFEST_PAGE_SIZE,
    (page + 1) * MANIFEST_PAGE_SIZE,
  )
  const totalCharacters = manifest.reduce(
    (sum, chapter) => sum + chapter.character_count,
    0,
  )

  return (
    <div className="book-delivery-workbench">
      <nav className="book-delivery-rail" aria-label="成书交付文件">
        <header>
          <div>
            <Layers3 size={13} />
            <span>交付文件</span>
          </div>
          <strong>{receipts.length}</strong>
        </header>
        <div className="book-delivery-file-list">
          {receipts.map((receipt) => {
            const selected = receipt.export_id === selectedReceipt.export_id
            const state = downloadStates[receipt.export_id] ?? "idle"
            return (
              <button
                aria-current={selected ? "true" : undefined}
                className={selected ? "is-active" : ""}
                key={receipt.export_id}
                onClick={() => onSelectReceipt(receipt)}
                type="button"
              >
                <span className="book-delivery-file-icon">
                  <FormatIcon format={receipt.format} />
                </span>
                <span>
                  <strong>{bookDeliveryFormatLabel(receipt.format)}</strong>
                  <small>{formatBookDeliveryBytes(receipt.size_bytes)}</small>
                  <i>{fileStateLabel(state)}</i>
                </span>
                <em aria-hidden="true" />
              </button>
            )
          })}
        </div>
        <footer>
          <LockKeyhole size={12} />
          <span>格式、正文版本和正式封面来自冻结 Export Artifact</span>
        </footer>
      </nav>

      <main className="book-delivery-canvas">
        <div className="book-delivery-canvas-inner">
          <header className="book-delivery-title">
            <div>
              <span>BOOK DELIVERY · FINAL</span>
              <h1>{artifact.title}</h1>
              <p>
                {artifact.author ? `作者 ${artifact.author}` : "未署名"}
                {artifact.version_note ? ` · ${artifact.version_note}` : ""}
              </p>
            </div>
            <button
              className="btn btn-primary text-xs"
              disabled={
                downloadStates[selectedReceipt.export_id] === "downloading"
              }
              onClick={() => onDownload(selectedReceipt)}
              type="button"
            >
              <Download size={13} />
              {downloadStates[selectedReceipt.export_id] === "downloading"
                ? "校验文件"
                : `下载 ${bookDeliveryFormatLabel(selectedReceipt.format)}`}
            </button>
          </header>

          <section className="book-delivery-integrity" aria-label="成书完整性">
            <Metric
              icon={<ShieldCheck size={16} />}
              label="完整性"
              value="全部通过"
            />
            <Metric
              icon={<BookOpenText size={16} />}
              label="正文单元"
              value={`${manifest.length} committed`}
            />
            <Metric
              icon={<FileText size={16} />}
              label="正文字符"
              value={totalCharacters.toLocaleString("zh-CN")}
            />
            <Metric
              icon={<BookCheck size={16} />}
              label="结构层级"
              value={
                artifact.volume_refs.length
                  ? `${artifact.volume_refs.length} 卷`
                  : "单体成书"
              }
            />
          </section>

          <div className="book-delivery-overview">
            <section className="book-delivery-cover" aria-label="正式封面">
              <div>
                <img
                  alt={`${artifact.title} 正式封面`}
                  src={bookCoverUrl(runId, artifact.cover_asset_ref)}
                />
              </div>
              <span>
                <ImageIcon size={11} /> 正式资产已嵌入全部格式
              </span>
            </section>

            <section className="book-delivery-manifest">
              <header>
                <div>
                  <span>CHAPTER MANIFEST</span>
                  <h2>正文版本清单</h2>
                </div>
                <p>交付回执直接投影，不逐章补查 Artifact</p>
              </header>
              <div className="book-delivery-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">序</th>
                      <th scope="col">标题</th>
                      <th scope="col">结构</th>
                      <th scope="col">字符</th>
                      <th scope="col">版本</th>
                      <th scope="col">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((chapter) => (
                      <tr key={chapter.chapter_ref}>
                        <td>{String(chapter.ordinal).padStart(3, "0")}</td>
                        <td>
                          <strong>{chapter.title}</strong>
                          <code>{chapter.chapter_ref}</code>
                        </td>
                        <td>
                          <span>
                            {chapter.unit_kind === "section" ? "段落" : "章节"}
                          </span>
                          <small>
                            {volumeLabel(chapter, artifact.volume_refs)}
                          </small>
                        </td>
                        <td>
                          {chapter.character_count.toLocaleString("zh-CN")}
                        </td>
                        <td>
                          <code>{shortVersion(chapter.version_ref)}</code>
                        </td>
                        <td>
                          <span className="is-valid">
                            <CheckCircle2 size={12} /> 已冻结
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {pageCount > 1 ? (
                <footer className="book-delivery-pagination">
                  <span>
                    {page * MANIFEST_PAGE_SIZE + 1}-
                    {Math.min((page + 1) * MANIFEST_PAGE_SIZE, manifest.length)}{" "}
                    / {manifest.length}
                  </span>
                  <div>
                    <button
                      aria-label="上一页正文清单"
                      disabled={page === 0}
                      onClick={() =>
                        setRequestedPage((value) => Math.max(0, value - 1))
                      }
                      type="button"
                    >
                      <ChevronLeft size={13} />
                    </button>
                    <button
                      aria-label="下一页正文清单"
                      disabled={page === pageCount - 1}
                      onClick={() =>
                        setRequestedPage((value) =>
                          Math.min(pageCount - 1, value + 1),
                        )
                      }
                      type="button"
                    >
                      <ChevronRight size={13} />
                    </button>
                  </div>
                </footer>
              ) : null}
            </section>
          </div>
        </div>
      </main>

      <BookDeliveryReceipt
        artifactDigest={artifactDigest}
        downloadState={downloadStates[selectedReceipt.export_id] ?? "idle"}
        receipt={selectedReceipt}
      />
    </div>
  )
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <div>
      {icon}
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
      </span>
    </div>
  )
}

function FormatIcon({ format }: { format: Receipt["format"] }) {
  if (format === "epub") return <FileArchive size={14} />
  if (format === "docx") return <FileType2 size={14} />
  return <FileCode2 size={14} />
}

function fileStateLabel(state: BookDeliveryDownloadState) {
  if (state === "downloading") return "正在校验"
  if (state === "downloaded") return "已下载"
  if (state === "error") return "下载失败"
  return "文件就绪"
}

function bookCoverUrl(runId: string, assetRef: string) {
  return `/api/runs/${encodeURIComponent(runId)}/cover-assets/${encodeURIComponent(assetRef)}`
}

function volumeLabel(chapter: BookDeliveryChapterRow, volumeRefs: string[]) {
  if (!chapter.volume_ref) return "单体结构"
  const index = volumeRefs.indexOf(chapter.volume_ref)
  return index >= 0 ? `第 ${index + 1} 卷` : chapter.volume_ref
}

function shortVersion(value: string) {
  const suffix = value.replace(/^p32-text-committed-/, "")
  return suffix ? `${suffix.slice(0, 8)}…${suffix.slice(-6)}` : "-"
}
