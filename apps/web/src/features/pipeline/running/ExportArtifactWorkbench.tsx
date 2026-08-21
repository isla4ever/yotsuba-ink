import {
  Check,
  FileArchive,
  FileJson2,
  FileText,
  Image,
  ImageOff,
  ShieldCheck,
  ShieldX,
} from "lucide-react"
import type { CoverAssetRecord } from "../contracts/coverAsset"
import type { ExportArtifact } from "../contracts/delivery"
import type { ChapterVersionRecord } from "../contracts/run"
import { coverAssetContentUrl } from "../services/coverAssetApi"
import type { useExportDelivery } from "../state/useExportDelivery"
import { ExportDeliveryReceipt } from "./ExportDeliveryReceipt"

type FormatMeta = {
  id: ExportArtifact["format"]
  label: string
  detail: string
  icon: typeof FileArchive
}

const FORMATS: FormatMeta[] = [
  { id: "zip", label: "ZIP", detail: "完整作品包", icon: FileArchive },
  { id: "md", label: "Markdown", detail: "连续正文", icon: FileText },
  { id: "json", label: "JSON", detail: "结构化交付", icon: FileJson2 },
]

export function ExportArtifactWorkbench({
  artifact,
  committed,
  coverMatches,
  decision,
  delivery,
  onChange,
  parserReady,
  runId,
  selectedCover,
  versionRecords,
  versionsReady,
}: {
  artifact: ExportArtifact
  committed: boolean
  coverMatches: boolean
  decision: boolean
  delivery: ReturnType<typeof useExportDelivery>
  onChange: (artifact: ExportArtifact) => void
  parserReady: boolean
  runId: string
  selectedCover: CoverAssetRecord | undefined
  versionRecords: Map<string, ChapterVersionRecord>
  versionsReady: boolean
}) {
  const manifestRows = buildManifestRows(artifact)
  return (
    <main className="max-w-6xl mx-auto px-4 md:px-6 py-5 md:py-7">
      <header className="flex flex-col md:flex-row md:items-end gap-3 justify-between mb-5">
        <div>
          <span className="text-[10px] font-mono text-fog uppercase tracking-wider">
            {decision ? "候选清单 · 等待作者确认" : "不可变交付 · 只读"}
          </span>
          <h1 className="font-serif text-xl font-semibold text-ink mt-1">
            {artifact.metadata.title}
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="badge badge-action">
            {artifact.format.toUpperCase()}
          </span>
          <span className="badge badge-ash">{artifact.volumes.length} 卷</span>
          <span className="badge badge-mint">
            {artifact.chapter_version_ids.length} 章已锁定
          </span>
        </div>
      </header>

      <ReadinessStrip
        coverMatches={coverMatches}
        hasCover={Boolean(artifact.cover_asset_id)}
        parserReady={parserReady}
        versionsReady={versionsReady}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.72fr)] gap-6 mt-6">
        <div className="min-w-0 space-y-7">
          <ExportConfiguration
            artifact={artifact}
            editable={decision}
            onChange={onChange}
          />
          <ManifestTable rows={manifestRows} versionRecords={versionRecords} />
        </div>

        <aside className="min-w-0 space-y-4 xl:sticky xl:top-0 self-start">
          <CoverBinding
            asset={selectedCover}
            assetId={artifact.cover_asset_id}
            runId={runId}
          />
          <ExportDeliveryReceipt delivery={delivery} committed={committed} />
        </aside>
      </div>
    </main>
  )
}

function ExportConfiguration({
  artifact,
  editable,
  onChange,
}: {
  artifact: ExportArtifact
  editable: boolean
  onChange: (artifact: ExportArtifact) => void
}) {
  return (
    <section>
      <SectionTitle title="交付配置" detail="确认后物化为不可变文件" />
      <div
        className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3"
        role="group"
        aria-label="导出格式"
      >
        {FORMATS.map((format) => {
          const Icon = format.icon
          const active = artifact.format === format.id
          return (
            <button
              type="button"
              key={format.id}
              aria-pressed={active}
              disabled={!editable}
              onClick={() => onChange({ ...artifact, format: format.id })}
              className={`text-left flex items-center gap-3 border rounded-lg p-3 transition-colors ${
                active
                  ? "border-action bg-action-bg"
                  : "border-hairline bg-surface hover:bg-hover"
              } disabled:cursor-default`}
            >
              <Icon
                size={16}
                className={active ? "text-action" : "text-fog"}
              />
              <span>
                <strong className="text-xs text-ink block">
                  {format.label}
                </strong>
                <small className="text-[10px] text-fog block mt-0.5">
                  {format.detail}
                </small>
              </span>
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <label>
          <span className="text-xs text-ash block mb-1.5">正式书名</span>
          <input
            className="input font-serif"
            value={artifact.metadata.title}
            readOnly
          />
        </label>
        <label>
          <span className="text-xs text-ash block mb-1.5">作者署名</span>
          <input
            className="input"
            value={artifact.metadata.author}
            readOnly={!editable}
            placeholder="未填写作者署名"
            onChange={(event) =>
              onChange({
                ...artifact,
                metadata: { ...artifact.metadata, author: event.target.value },
              })
            }
          />
        </label>
      </div>
      <label className="block mt-3">
        <span className="text-xs text-ash block mb-1.5">版本说明</span>
        <textarea
          className="input"
          rows={3}
          value={artifact.metadata.version_note}
          readOnly={!editable}
          onChange={(event) =>
            onChange({
              ...artifact,
              metadata: {
                ...artifact.metadata,
                version_note: event.target.value,
              },
            })
          }
        />
      </label>
    </section>
  )
}

function ManifestTable({
  rows,
  versionRecords,
}: {
  rows: ManifestRow[]
  versionRecords: Map<string, ChapterVersionRecord>
}) {
  return (
    <section>
      <SectionTitle
        title="卷章清单"
        detail={`${rows.filter((row) => row.type === "volume").length} 卷 · ${rows.filter((row) => row.type === "chapter").length} 个不可变正文版本`}
      />
      <div className="border border-hairline rounded-lg overflow-hidden mt-3 bg-surface">
        <div className="grid grid-cols-[42px_minmax(0,1fr)_minmax(120px,0.7fr)_72px] gap-2 px-3 py-2 bg-hover text-[10px] text-fog uppercase tracking-wider">
          <span>#</span>
          <span>章节</span>
          <span>版本</span>
          <span>状态</span>
        </div>
        <div className="max-h-[560px] overflow-y-auto">
          {rows.map((row) => {
            if (row.type === "volume") {
              return (
                <div
                  key={row.key}
                  className="flex items-center justify-between gap-3 px-3 py-2.5 border-t border-hairline bg-base"
                >
                  <strong className="text-xs text-ink">{row.title}</strong>
                  <span className="text-[10px] text-fog">
                    {row.chapterCount} 章
                  </span>
                </div>
              )
            }
            const record = versionRecords.get(row.versionId)
            const accepted = record?.artifact.author_status === "accepted"
            return (
              <div
                key={row.key}
                className="grid grid-cols-[42px_minmax(0,1fr)_minmax(120px,0.7fr)_72px] items-center gap-2 px-3 py-2.5 border-t border-ghost"
              >
                <span className="text-[10px] font-mono text-fog">
                  {String(row.index).padStart(2, "0")}
                </span>
                <strong className="text-xs text-ink truncate">
                  {record?.artifact.title || `第 ${row.index} 章`}
                </strong>
                <code
                  className="text-[10px] text-fog truncate"
                  title={row.versionId}
                >
                  {row.versionId}
                </code>
                <span
                  className={`text-[10px] flex items-center gap-1 ${accepted ? "text-mint" : "text-risk"}`}
                >
                  {accepted ? <Check size={11} /> : <ShieldX size={11} />}
                  {accepted ? "已接受" : "不匹配"}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

function CoverBinding({
  asset,
  assetId,
  runId,
}: {
  asset: CoverAssetRecord | undefined
  assetId: string
  runId: string
}) {
  return (
    <section className="border border-hairline rounded-lg bg-surface overflow-hidden">
      <header className="px-4 py-3 border-b border-hairline flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink flex items-center gap-2">
          <Image size={13} className="text-fog" /> 正式封面
        </span>
        <span className="badge badge-ash">
          {assetId ? "已绑定" : "不含图片"}
        </span>
      </header>
      {asset ? (
        <img
          src={coverAssetContentUrl(runId, asset)}
          alt="正式封面"
          className="w-full aspect-[2/3] object-cover"
        />
      ) : (
        <div className="aspect-[4/3] grid place-items-center text-center px-5">
          <div>
            <ImageOff size={24} className="text-fog mx-auto mb-3" />
            <p className="text-xs text-ash">
              {assetId
                ? "正式封面资产暂未读取"
                : "本次冻结配置不包含封面图片"}
            </p>
          </div>
        </div>
      )}
      <div className="px-4 py-3 border-t border-hairline">
        <code className="text-[10px] text-fog break-all">
          {assetId || "cover_asset_id: empty"}
        </code>
      </div>
    </section>
  )
}

function ReadinessStrip({
  coverMatches,
  hasCover,
  parserReady,
  versionsReady,
}: {
  coverMatches: boolean
  hasCover: boolean
  parserReady: boolean
  versionsReady: boolean
}) {
  const checks = [
    {
      label: "Artifact 合同",
      detail: parserReady ? "字段与卷章分组有效" : "合同无效",
      ready: parserReady,
    },
    {
      label: "正文版本",
      detail: versionsReady ? "全部指向已接受版本" : "存在缺失或非接受版本",
      ready: versionsReady,
    },
    {
      label: "封面绑定",
      detail: coverMatches
        ? hasCover
          ? "与正式封面一致"
          : "按配置不含图片"
        : "与 Cover Artifact 不一致",
      ready: coverMatches,
    },
  ]
  return (
    <div
      className="grid grid-cols-1 md:grid-cols-3 gap-px border border-hairline rounded-lg overflow-hidden bg-hairline"
      aria-label="交付准备度"
    >
      {checks.map((check) => (
        <div
          key={check.label}
          className="bg-surface px-4 py-3 flex items-start gap-2.5"
        >
          {check.ready ? (
            <ShieldCheck size={15} className="text-mint mt-0.5 shrink-0" />
          ) : (
            <ShieldX size={15} className="text-risk mt-0.5 shrink-0" />
          )}
          <div>
            <strong className="text-xs text-ink block">{check.label}</strong>
            <span className="text-[10px] text-fog block mt-0.5">
              {check.detail}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

type ManifestRow =
  | { type: "volume"; key: string; title: string; chapterCount: number }
  | { type: "chapter"; key: string; index: number; versionId: string }

function buildManifestRows(artifact: ExportArtifact): ManifestRow[] {
  const rows: ManifestRow[] = []
  let chapterIndex = 0
  artifact.volumes.forEach((volume, volumeIndex) => {
    rows.push({
      type: "volume",
      key: `volume-${volumeIndex + 1}`,
      title: `第 ${volumeIndex + 1} 卷 · ${volume.title}`,
      chapterCount: volume.chapter_count,
    })
    for (let offset = 0; offset < volume.chapter_count; offset += 1) {
      const versionId = artifact.chapter_version_ids[chapterIndex]
      chapterIndex += 1
      rows.push({
        type: "chapter",
        key: versionId,
        index: chapterIndex,
        versionId,
      })
    }
  })
  return rows
}

function SectionTitle({ detail, title }: { detail: string; title: string }) {
  return (
    <div className="flex items-end justify-between gap-3">
      <h2 className="text-xs font-medium text-ink">{title}</h2>
      <span className="text-[10px] text-fog text-right">{detail}</span>
    </div>
  )
}
