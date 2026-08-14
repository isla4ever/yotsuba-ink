import { CheckCircle2, Download, FileArchive, FileJson2, FileText, Image, ImageOff, LoaderCircle, ShieldCheck, ShieldX } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { coverAssetUrl } from '../services/coverAssetApi';
import { useExportDelivery } from '../state/useExportDelivery';
import { parseExportArtifact, type ExportArtifactVnext } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  deliveryRevision: string;
  onArtifactChange: (artifact: ExportArtifactVnext) => void;
  readOnly: boolean;
  result: string;
  runId: string;
};

const FORMATS: Array<{ id: ExportArtifactVnext['format']; label: string; icon: typeof FileArchive }> = [
  { id: 'zip', label: 'ZIP', icon: FileArchive },
  { id: 'md', label: 'Markdown', icon: FileText },
  { id: 'json', label: 'JSON', icon: FileJson2 },
];

export function ExportStageViewVnext({ deliveryRevision, onArtifactChange, readOnly, result, runId }: Props) {
  const parsed = useMemo(() => parseExportArtifact(result), [result]);
  const [artifact, setArtifact] = useState<ExportArtifactVnext | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  const delivery = useExportDelivery(runId, artifact, readOnly, deliveryRevision);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Export Artifact" />;
  const update = (next: ExportArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  return (
    <div className="vnext-artifact-workbench export-vnext">
      <section className="vnext-artifact-section vnext-export-package">
        <header><div><span>交付包</span><strong><FileArchive size={15} />{artifact.format.toUpperCase()}</strong></div></header>
        <div aria-label="导出格式" className="vnext-export-format" role="group">
          {FORMATS.map((format) => {
            const Icon = format.icon;
            return <button aria-pressed={artifact.format === format.id} disabled={readOnly} key={format.id} onClick={() => update({ ...artifact, format: format.id })} type="button"><Icon size={15} />{format.label}</button>;
          })}
        </div>
        <div className="vnext-export-cover-row">
          {artifact.cover_asset_id
            ? <img alt="正式封面" src={coverAssetUrl(runId, artifact.cover_asset_id)} />
            : <span aria-hidden="true" className="vnext-export-cover-empty"><ImageOff size={16} /></span>}
          <div>
            <Image size={15} />
            <span>正式封面</span>
            <strong>{artifact.cover_asset_id || '未绑定封面资产'}</strong>
          </div>
        </div>
        <div className="vnext-field-grid">
          <label className="vnext-field"><span>书名</span><input readOnly value={artifact.metadata.title} /></label>
          <label className="vnext-field"><span>作者</span><input onChange={(event) => update({ ...artifact, metadata: { ...artifact.metadata, author: event.target.value } })} readOnly={readOnly} value={artifact.metadata.author} /></label>
        </div>
        <label className="vnext-field"><span>版本说明</span><textarea onChange={(event) => update({ ...artifact, metadata: { ...artifact.metadata, version_note: event.target.value } })} readOnly={readOnly} rows={3} value={artifact.metadata.version_note} /></label>
      </section>
      <section className="vnext-artifact-section">
        <header><div><span>已接受章节版本</span><strong>{artifact.chapter_version_ids.length} 章</strong></div></header>
        <div className="vnext-version-list">{artifact.chapter_version_ids.map((versionId, index) => <div key={versionId}><span>{String(index + 1).padStart(2, '0')}</span><strong>{versionId}</strong><CheckCircle2 size={15} /></div>)}</div>
      </section>
      {readOnly ? <ExportDeliveryReceipt delivery={delivery} /> : null}
    </div>
  );
}

function ExportDeliveryReceipt({ delivery }: { delivery: ReturnType<typeof useExportDelivery> }) {
  const receipt = delivery.receipt;
  const pending = delivery.status === 'loading' || delivery.status === 'downloading';
  return (
    <section aria-live="polite" className={`vnext-artifact-section vnext-export-receipt ${delivery.status}`}>
      <header>
        <div>
          {pending ? <LoaderCircle size={15} /> : receipt ? <ShieldCheck size={15} /> : <ShieldX size={15} />}
          <span>不可变交付回执</span>
          <strong>{receipt ? '校验可下载' : deliveryStatusLabel(delivery.status)}</strong>
        </div>
        {receipt ? (
          <button className="vnext-add-command" disabled={pending} onClick={() => void delivery.download()} type="button">
            <Download size={15} />{delivery.status === 'downloading' ? '校验中' : '校验并下载'}
          </button>
        ) : null}
      </header>
      {receipt ? (
        <dl>
          <div><dt>文件</dt><dd>{receipt.filename}</dd></div>
          <div><dt>大小</dt><dd>{formatBytes(receipt.size_bytes)}</dd></div>
          <div><dt>SHA-256</dt><dd><code>{receipt.sha256}</code></dd></div>
          <div><dt>物化时间</dt><dd>{receipt.created_at}</dd></div>
        </dl>
      ) : null}
    </section>
  );
}

function deliveryStatusLabel(status: ReturnType<typeof useExportDelivery>['status']) {
  if (status === 'loading') return '读取回执';
  if (status === 'missing') return '尚未物化';
  if (status === 'error') return '回执不可用';
  return '等待定稿';
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(1)} KB`;
}
