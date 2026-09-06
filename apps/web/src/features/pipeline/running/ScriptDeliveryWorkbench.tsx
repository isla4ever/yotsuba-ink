import {
  CheckCircle2,
  Clapperboard,
  Download,
  FileCode2,
  FileText,
  FileType2,
  Layers3,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react"
import {
  deliveryFormatLabel,
  formatDeliveryBytes,
  type ScriptDeliveryArtifact,
  type ScriptDeliveryReceipt,
  type ScriptDeliverySceneRow,
} from "../lib/phase32ScriptDelivery"
import { ScriptDeliveryReceipt as DeliveryReceiptPanel } from "./ScriptDeliveryReceipt"

export type DeliveryDownloadState = "idle" | "downloading" | "downloaded" | "error"

type Props = {
  artifact: ScriptDeliveryArtifact
  artifactDigest: string
  downloadStates: Record<string, DeliveryDownloadState>
  manifest: ScriptDeliverySceneRow[]
  onDownload: (receipt: ScriptDeliveryReceipt) => void
  onSelectReceipt: (receipt: ScriptDeliveryReceipt) => void
  receipts: ScriptDeliveryReceipt[]
  selectedReceipt: ScriptDeliveryReceipt
}

export function ScriptDeliveryWorkbench({
  artifact,
  artifactDigest,
  downloadStates,
  manifest,
  onDownload,
  onSelectReceipt,
  receipts,
  selectedReceipt,
}: Props) {
  const validSceneCount = manifest.filter((scene) => scene.valid).length
  const totalBlocks = manifest.reduce((sum, scene) => sum + scene.blockCount, 0)

  return (
    <div className="script-delivery-workbench">
      <nav className="script-delivery-rail" aria-label="交付文件">
        <header>
          <div>
            <Layers3 size={13} />
            <span>交付文件</span>
          </div>
          <strong>{receipts.length}</strong>
        </header>
        <div className="script-delivery-file-list">
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
                <span className="script-delivery-file-icon">
                  <FormatIcon format={receipt.format} />
                </span>
                <span>
                  <strong>{deliveryFormatLabel(receipt.format)}</strong>
                  <small>{formatDeliveryBytes(receipt.size_bytes)}</small>
                  <i>{fileStateLabel(state)}</i>
                </span>
                <em aria-hidden="true" />
              </button>
            )
          })}
        </div>
        <footer>
          <LockKeyhole size={12} />
          <span>格式来自创建时冻结的流水线配置</span>
        </footer>
      </nav>

      <main className="script-delivery-canvas">
        <div className="script-delivery-canvas-inner">
          <header className="script-delivery-title">
            <div>
              <span>SCREENPLAY DELIVERY · FINAL</span>
              <h1>{artifact.title}</h1>
              <p>
                {artifact.author ? `编剧 ${artifact.author}` : "未署名"}
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
                : `下载 ${deliveryFormatLabel(selectedReceipt.format)}`}
            </button>
          </header>

          <section
            className="script-delivery-integrity"
            aria-label="交付完整性"
          >
            <div>
              <ShieldCheck size={16} />
              <span>
                <small>完整性</small>
                <strong>
                  {validSceneCount === manifest.length
                    ? "全部通过"
                    : "存在缺口"}
                </strong>
              </span>
            </div>
            <div>
              <Clapperboard size={16} />
              <span>
                <small>Scene 清单</small>
                <strong>
                  {validSceneCount} / {manifest.length}
                </strong>
              </span>
            </div>
            <div>
              <FileText size={16} />
              <span>
                <small>正文块</small>
                <strong>{totalBlocks}</strong>
              </span>
            </div>
            <div>
              <CheckCircle2 size={16} />
              <span>
                <small>来源版本</small>
                <strong>{manifest.length} committed</strong>
              </span>
            </div>
          </section>

          <section className="script-delivery-manifest">
            <header>
              <div>
                <span>SCENE MANIFEST</span>
                <h2>交付内容清单</h2>
              </div>
              <p>冻结顺序与剧本正文逐场版本一一对应</p>
            </header>
            <div className="script-delivery-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">序</th>
                    <th scope="col">Scene</th>
                    <th scope="col">版本来源</th>
                    <th scope="col">正文构成</th>
                    <th scope="col">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {manifest.map((scene) => (
                    <tr key={scene.sceneRef}>
                      <td>{String(scene.ordinal).padStart(2, "0")}</td>
                      <td>
                        <strong>{scene.heading}</strong>
                        <code>{scene.sceneRef}</code>
                      </td>
                      <td>
                        <code>{shortVersion(scene.versionRef)}</code>
                      </td>
                      <td>
                        <span>{scene.blockCount} 块</span>
                        <small>
                          {scene.actionBlocks} 动作 · {scene.dialogueBlocks}{" "}
                          对白
                        </small>
                      </td>
                      <td>
                        <span
                          className={scene.valid ? "is-valid" : "is-invalid"}
                        >
                          {scene.valid ? <CheckCircle2 size={12} /> : null}
                          {scene.valid ? "已核验" : "缺失"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </main>

      <DeliveryReceiptPanel
        artifactDigest={artifactDigest}
        downloadState={downloadStates[selectedReceipt.export_id] ?? "idle"}
        receipt={selectedReceipt}
        sceneCount={manifest.length}
      />
    </div>
  )
}

function FormatIcon({ format }: { format: ScriptDeliveryReceipt["format"] }) {
  if (format === "fountain") return <FileCode2 size={14} />
  if (format === "pdf") return <FileType2 size={14} />
  return <FileText size={14} />
}

function fileStateLabel(state: DeliveryDownloadState) {
  if (state === "downloading") return "正在校验"
  if (state === "downloaded") return "已下载"
  if (state === "error") return "下载失败"
  return "文件就绪"
}

function shortVersion(value: string) {
  const suffix = value.replace(/^p32-script-committed-/, "")
  return suffix ? `${suffix.slice(0, 8)}…${suffix.slice(-6)}` : "-"
}
