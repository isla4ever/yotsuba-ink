import { Download, FileArchive, RotateCcw } from 'lucide-react';
import type { ExportReceipt } from '../contracts';
import { formatFileSize, formatHistoryTime } from '../lib/display';
import { LoadingButton } from './LoadingButton';

type Props = {
  error: string;
  fallbackReceipt: ExportReceipt | null;
  items: ExportReceipt[];
  loading: boolean;
  onDownload: (receipt: ExportReceipt) => void;
  onRefresh: () => void;
  pendingAction: string;
};

export function HistoryExportVersions({
  error,
  fallbackReceipt,
  items,
  loading,
  onDownload,
  onRefresh,
  pendingAction,
}: Props) {
  const receipts = items.length ? items : fallbackReceipt ? [fallbackReceipt] : [];

  if (!receipts.length && !loading && !error) return null;

  return (
    <section aria-label="交付版本" className="history-export-versions">
      <div className="history-export-versions-head">
        <div>
          <strong><FileArchive size={14} />交付版本</strong>
          <span>{loading ? '正在同步' : `${receipts.length} 个不可变版本`}</span>
        </div>
        <LoadingButton
          aria-label="刷新交付版本"
          className="icon-button history-export-refresh"
          loading={loading}
          loadingLabel={null}
          onClick={onRefresh}
          title="刷新交付版本"
        >
          <RotateCcw size={14} />
        </LoadingButton>
      </div>
      {error ? <p className="history-inline-error" role="alert">{error}</p> : null}
      <div className="history-export-version-list">
        {receipts.map((receipt, index) => {
          const downloading = pendingAction.endsWith(`:${receipt.export_id}`);
          const versionLabel = index === 0 ? '最新' : `#${receipts.length - index}`;
          return (
            <article className="history-export-version" key={receipt.export_id}>
              <span className="history-export-version-index">{versionLabel}</span>
              <div className="history-export-version-main">
                <strong title={receipt.filename}>{receipt.filename}</strong>
                <span>
                  {receipt.format.toUpperCase()} · {receipt.chapter_version_ids.length} 章 · {formatFileSize(receipt.size_bytes)} · {formatHistoryTime(receipt.created_at)}
                </span>
                <small>
                  {receipt.metadata.author || '未署名'}
                  {receipt.metadata.version_note ? ` · ${receipt.metadata.version_note}` : ''}
                  {receipt.cover_asset_id ? ` · 封面 ${receipt.cover_asset_id}` : ''}
                  {receipt.artifact_signature ? ` · 产物 ${receipt.artifact_signature.slice(0, 8)}` : ''}
                  {receipt.sha256 ? ` · SHA ${receipt.sha256.slice(0, 8)}` : ''}
                </small>
              </div>
              <LoadingButton
                aria-label={`下载交付版本 ${receipt.filename}`}
                className="icon-button history-export-download"
                disabled={Boolean(pendingAction)}
                loading={downloading}
                loadingLabel={null}
                onClick={() => onDownload(receipt)}
                title={`下载 ${receipt.filename}`}
              >
                <Download size={14} />
              </LoadingButton>
            </article>
          );
        })}
      </div>
    </section>
  );
}
