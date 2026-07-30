import { AlertTriangle, CheckCircle2, Clock3, Download, FileText, PackageCheck, ShieldCheck } from 'lucide-react';
import type { ExportReceipt } from '../contracts';
import { LoadingButton } from '../layout/LoadingButton';
import { formatFileSize } from '../lib/display';
import type { ExportSelectionSnapshot } from './exportSelectionModel';
import { exportPackageName } from './exportSelectionModel';
import type { ExportArtifact } from './stageArtifacts';
import { exportValidationRows, exportValidationValue } from './exportValidation';

export function ExportDeliveryPanel({
  artifact,
  activeSelection,
  currentSelection,
  downloading,
  error,
  generatedSelection,
  generating,
  onDownload,
  onGenerate,
  onPreview,
  previewing,
  receipt,
  selectionChanged,
}: {
  activeSelection: ExportSelectionSnapshot | null;
  artifact: ExportArtifact;
  currentSelection: ExportSelectionSnapshot;
  downloading: boolean;
  error: string;
  generatedSelection: ExportSelectionSnapshot | null;
  generating: boolean;
  onDownload: () => void;
  onGenerate: () => void;
  onPreview: () => void;
  previewing: boolean;
  receipt: ExportReceipt | null;
  selectionChanged: boolean;
}) {
  const displayedSelection = activeSelection ?? generatedSelection ?? currentSelection;
  const displayedReceipt = activeSelection ? null : receipt;
  const packageName = displayedReceipt?.filename || exportPackageName(displayedSelection, artifact.bundle_name);
  const manifestRows = buildManifestRows(artifact.files, packageName, displayedSelection.format, displayedSelection.chapter_ids.length);
  const canGenerate = Boolean(currentSelection.chapter_ids.length && artifact.package_ready);
  const frozenChapterNames = displayedSelection.chapter_ids.map((id) => artifact.chapters?.find((chapter) => chapter.id === id)?.title || id);
  const frozenMetadata = metadataSummary(displayedSelection, artifact);

  return (
    <>
      <section aria-busy={generating || downloading || previewing} className="export-package-surface">
        <div className="export-section-head">
          <div><p className="eyebrow">版本冻结</p><h3><Download size={15} />交付包</h3></div>
          <strong>{displayedSelection.format.toUpperCase()}</strong>
        </div>
        <div className="export-package-hero">
          <FileText size={28} />
          <div>
            <strong>{packageName}</strong>
            <span>{displayedSelection.chapter_ids.length} 章正文 · {generating ? '选择已冻结，正在生成' : displayedReceipt ? '不可变交付版本' : '等待生成'}</span>
          </div>
        </div>
        <div className="export-manifest-table">
          {manifestRows.map((row) => <article key={row.name}><span>{row.format}</span><strong>{row.name}</strong><small>{row.status}</small></article>)}
        </div>
        {activeSelection || displayedReceipt ? (
          <dl className="export-frozen-selection">
            <div><dt>冻结章节</dt><dd>{frozenChapterNames.join(' / ')}</dd></div>
            <div><dt>交付元数据</dt><dd>{frozenMetadata}</dd></div>
          </dl>
        ) : null}
        {displayedReceipt ? (
          <div className="export-receipt-summary" aria-label="当前导出收据">
            <span title={displayedReceipt.export_id}><b>交付版本</b>V{displayedReceipt.version || 1} · {shortId(displayedReceipt.export_id)}</span>
            <span title={displayedReceipt.selection_digest}><b>冻结选择</b>{shortId(displayedReceipt.selection_digest)}</span>
            <span><b>源快照</b>{shortId(displayedReceipt.snapshot_id)}</span>
            <span title={displayedReceipt.sha256}><b>包 SHA-256</b>{shortId(displayedReceipt.sha256)}</span>
            <span title={displayedReceipt.cover_asset?.sha256 || ''}><b>封面资产</b>{coverReceiptLabel(displayedReceipt)}</span>
            <span><b>文件清单</b>{displayedReceipt.files.length} 项 · {formatFileSize(displayedReceipt.size_bytes)}</span>
          </div>
        ) : null}
        {selectionChanged ? <div className="export-selection-changed"><AlertTriangle size={14} />当前选择已变化；重新下载仍对应旧收据，生成新版本后才会更新。</div> : null}
        {error ? <div className="export-generation-error" role="alert"><AlertTriangle size={14} />{error}</div> : null}
        <div className="export-action-row refined">
          <LoadingButton className="ghost tiny-action" disabled={generating || downloading || previewing || !currentSelection.chapter_ids.length} loading={previewing} loadingLabel="生成预览中" onClick={onPreview}><Clock3 size={14} />下载预览稿</LoadingButton>
          <LoadingButton className="tech-button" disabled={generating || downloading || !canGenerate} loading={generating} loadingLabel="正在生成" onClick={onGenerate}><PackageCheck size={14} />{receipt ? '生成新版本' : '生成并下载'}</LoadingButton>
          <LoadingButton className="ghost tiny-action" disabled={!receipt || generating || downloading} loading={downloading} loadingLabel="正在下载" onClick={onDownload}><Download size={14} />重新下载</LoadingButton>
        </div>
      </section>
      <ExportValidationPanel artifact={artifact} generating={generating} receipt={receipt} selectionChanged={selectionChanged} />
    </>
  );
}

function ExportValidationPanel({ artifact, generating, receipt, selectionChanged }: { artifact: ExportArtifact; generating: boolean; receipt: ExportReceipt | null; selectionChanged: boolean }) {
  const stateLabel = generating ? '生成中' : selectionChanged ? '选择已变化' : receipt ? '已生成' : '待生成';
  return (
    <section className="export-validation-surface">
      <div className="export-section-head"><div><p className="eyebrow">交付检查</p><h3><ShieldCheck size={15} />校验状态</h3></div><span>{stateLabel}</span></div>
      <div className="export-validation-ledger">
        {exportValidationRows(artifact.validation).map((row) => {
          const Icon = row.status === 'ready' ? CheckCircle2 : row.status === 'pending' ? Clock3 : AlertTriangle;
          return <article className={row.status} key={row.key}><Icon size={13} /><strong>{row.label}</strong><span>{row.value}</span></article>;
        })}
      </div>
    </section>
  );
}

function buildManifestRows(files: Array<{ name: string; format: string; status: string }>, packageName: string, outputKind: string, chapterCount: number) {
  const rows = outputKind === 'zip'
    ? [
      { name: packageName, format: 'zip', status: 'ready' },
      { name: `chapters/ · ${chapterCount} 个章节文件`, format: 'md', status: 'ready' },
      { name: 'manifest.json', format: 'json', status: 'ready' },
      { name: 'README.md', format: 'md', status: 'ready' },
      ...files.filter((file) => !file.name.startsWith('chapters.')),
    ]
    : [{ name: packageName, format: outputKind, status: 'ready' }];
  return rows.slice(0, 6).map((file) => ({
    name: file.name,
    status: exportValidationValue(file.status),
    format: file.format?.toUpperCase() || outputKind.toUpperCase(),
  }));
}

function metadataSummary(selection: ExportSelectionSnapshot, artifact: ExportArtifact) {
  const metadata = selection.metadata;
  return [metadata.title || artifact.metadata.title || '沿用作品标题', metadata.author, metadata.version_note]
    .filter(Boolean)
    .join(' · ');
}

function shortId(value: string) {
  if (!value) return '未返回';
  return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function coverReceiptLabel(receipt: ExportReceipt) {
  const cover = receipt.cover_asset;
  if (!cover) return '未记录';
  return `${cover.candidate_id || '正式封面'} · ${shortId(cover.sha256)}`;
}
