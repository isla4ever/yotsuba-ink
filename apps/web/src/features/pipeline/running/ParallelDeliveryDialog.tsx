import { Check, CircleDashed, Download, FileClock, Image, ShieldCheck, X } from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import type { ExportFormat, ExportMetadata } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { LoadingButton } from '../layout/LoadingButton';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { downloadRunExportPreview } from '../services/runApi';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { coverImageSource } from './coverPresentation';
import type { ParallelDeliverySnapshot } from './parallelDeliveryModel';
import type { WritingArtifact } from './writingArtifactModel';

type Props = {
  activeRunId: string;
  artifact: WritingArtifact;
  onClose: () => void;
  snapshot: ParallelDeliverySnapshot;
};

const FORMATS: ExportFormat[] = ['md', 'json', 'zip'];

export function ParallelDeliveryDialog({ activeRunId, artifact, onClose, snapshot }: Props) {
  const completed = useMemo(
    () => artifact.chapters.filter((chapter) => chapter.status === 'completed' && chapter.content.trim()),
    [artifact.chapters],
  );
  const completedIds = completed.map((chapter) => chapter.id).join('\u0000');
  const [selected, setSelected] = useState(() => completed.map((chapter) => chapter.id));
  const [format, setFormat] = useState<ExportFormat>('md');
  const [metadata, setMetadata] = useState<ExportMetadata>({ title: '', author: '', bundle_name: '', version_note: '连载预览' });
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState('');
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });

  useEffect(() => {
    const valid = new Set(completedIds ? completedIds.split('\u0000') : []);
    setSelected((current) => {
      const kept = current.filter((id) => valid.has(id));
      return kept.length ? kept : [...valid];
    });
  }, [completedIds]);

  const updateMetadata = (key: keyof ExportMetadata, value: string) => {
    setMetadata((current) => ({ ...current, [key]: value }));
  };
  const downloadPreview = async () => {
    if (!activeRunId || !selected.length || busy) return;
    const controller = new AbortController();
    setBusy(true);
    setFeedback('');
    try {
      const downloaded = await downloadRunExportPreview(activeRunId, format, selected, metadata, controller.signal);
      triggerBlobDownload(downloaded.blob, downloaded.filename);
      setFeedback(`${downloaded.filename} 已开始下载`);
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : '预览稿生成失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <motion.div animate="animate" className={`parallel-delivery-backdrop app-overlay-backdrop ${portalModeClass()}`} exit="exit" initial="initial" onClick={onClose} role="presentation" variants={backdropMotionVariants}>
      <motion.section
        animate="animate"
        aria-label="并行交付"
        aria-modal="true"
        className="parallel-delivery-dialog app-dialog-surface"
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <header className="parallel-delivery-head">
          <div><p className="eyebrow">细纲定稿后双轨推进</p><h2>并行交付</h2><span>{snapshot.message}</span></div>
          <span className={`parallel-delivery-state is-${snapshot.status}`}><DeliveryStateIcon status={snapshot.status} />{deliveryStatusLabel(snapshot.status)}</span>
          <button aria-label="关闭并行交付" className="modal-close" onClick={onClose} type="button"><X size={19} /></button>
        </header>

        <div className="parallel-delivery-body">
          <section className="parallel-cover-track" aria-label="封面并行进度">
            <div className="parallel-section-title"><span><Image size={14} />封面候选</span><strong>{snapshot.coverReady}/{snapshot.coverTotal || snapshot.cover.candidates.length}</strong></div>
            <div className="parallel-cover-stack" data-empty={!snapshot.cover.candidates.length || undefined}>
              {snapshot.cover.candidates.slice(0, 3).map((candidate, index) => {
                const source = coverImageSource(candidate.image_url);
                return (
                  <figure className={`is-${candidate.asset_status}`} key={candidate.id || index} style={{ '--cover-index': index } as CSSProperties}>
                    {source ? <img alt={`封面候选 ${index + 1}`} src={source} /> : <span><Image size={22} /><small>{assetStatusLabel(candidate.asset_status)}</small></span>}
                    <figcaption><b>{String(index + 1).padStart(2, '0')}</b><span>{candidate.palette || candidate.composition || '构图已规划'}</span></figcaption>
                  </figure>
                );
              })}
              {!snapshot.cover.candidates.length ? <div className="parallel-cover-empty"><CircleDashed size={26} /><strong>等待封面规划</strong><span>正文继续创作，不受封面轨阻塞。</span></div> : null}
            </div>
            <div className="parallel-cover-progress"><i><b style={{ width: `${snapshot.coverTotal ? (snapshot.coverReady / snapshot.coverTotal) * 100 : 0}%` }} /></i><span>{snapshot.coverReady ? '真实图片资产已落盘' : '封面任务正在并行准备'}</span></div>
          </section>

          <section className="parallel-preview-track" aria-label="章节预览导出">
            <div className="parallel-section-title"><span><FileClock size={14} />预览稿</span><strong>{selected.length}/{completed.length} 章</strong></div>
            <div className="parallel-preview-ledger">
              {completed.map((chapter, index) => (
                <button aria-pressed={selected.includes(chapter.id)} className={selected.includes(chapter.id) ? 'selected' : ''} key={chapter.id} onClick={() => setSelected((current) => current.includes(chapter.id) ? current.filter((id) => id !== chapter.id) : [...current, chapter.id])} type="button">
                  <span>{String(index + 1).padStart(2, '0')}</span><strong>{chapter.generated_title || chapter.title}</strong><small>{chapter.words.toLocaleString()} 字</small><i>{selected.includes(chapter.id) ? <Check size={12} /> : null}</i>
                </button>
              ))}
              {!completed.length ? <div className="parallel-preview-empty">完成第一章后即可下载预览稿</div> : null}
            </div>
            <div className="parallel-preview-config">
              <div className="parallel-format-control" role="radiogroup" aria-label="预览格式">
                {FORMATS.map((item) => <button aria-checked={format === item} className={format === item ? 'active' : ''} key={item} onClick={() => setFormat(item)} role="radio" type="button">{item.toUpperCase()}</button>)}
              </div>
              <label><span>作品标题</span><input maxLength={200} placeholder="沿用作品标题" value={metadata.title} onChange={(event) => updateMetadata('title', event.target.value)} /></label>
              <label><span>作者</span><input maxLength={160} placeholder="可选" value={metadata.author} onChange={(event) => updateMetadata('author', event.target.value)} /></label>
              <label><span>包名</span><input maxLength={160} placeholder="沿用作品标题" value={metadata.bundle_name} onChange={(event) => updateMetadata('bundle_name', event.target.value)} /></label>
              <label><span>版本说明</span><input maxLength={500} value={metadata.version_note} onChange={(event) => updateMetadata('version_note', event.target.value)} /></label>
            </div>
            <div className="parallel-preview-action">
              <span role="status">{feedback || '预览稿会随正文和封面变化，不生成最终收据。'}</span>
              <LoadingButton className="mode-primary-action" disabled={busy || !selected.length} loading={busy} loadingLabel="正在生成" onClick={() => void downloadPreview()}><Download size={14} />下载预览稿</LoadingButton>
            </div>
          </section>
        </div>

        <footer className="parallel-final-gates" aria-label="最终交付门禁">
          <div><span><ShieldCheck size={14} />最终交付门禁</span><small>预览不绕过最终校验</small></div>
          {snapshot.finalGates.map((gate) => (
            <article className={`is-${gate.state}`} key={gate.key}><DeliveryGateIcon state={gate.state} /><span><strong>{gate.label}</strong><small>{gate.detail}</small></span></article>
          ))}
        </footer>
      </motion.section>
    </motion.div>,
    document.body,
  );
}

function DeliveryStateIcon({ status }: { status: ParallelDeliverySnapshot['status'] }) {
  return status === 'running' ? <ButtonLoadingIndicator /> : status === 'ready' ? <Check size={13} /> : <CircleDashed size={13} />;
}

function DeliveryGateIcon({ state }: { state: ParallelDeliverySnapshot['finalGates'][number]['state'] }) {
  return state === 'ready' ? <Check size={13} /> : state === 'checking' ? <ShieldCheck size={13} /> : <CircleDashed size={13} />;
}

function deliveryStatusLabel(status: ParallelDeliverySnapshot['status']) {
  return { idle: '等待解锁', running: '并行推进中', ready: '候选已就绪', degraded: '可稍后重试', cancelled: '已暂停' }[status];
}

function assetStatusLabel(status: string) {
  return { planned: '等待生成', generating: '生成中', ready: '已就绪', failed: '可重试', blocked: '需处理' }[status] ?? '等待生成';
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function portalModeClass() {
  const shell = document.querySelector('.product-shell');
  return ['mode-fast', 'mode-balanced', 'mode-deep'].find((name) => shell?.classList.contains(name)) ?? '';
}
