import { useEffect, useRef, useState, type DragEvent } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { DatabaseZap, FileText, Trash2, UploadCloud, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import type { KnowledgeDocument, QualityMode } from '../contracts';
import { DangerConfirmationDialog } from '../layout/DangerConfirmationDialog';
import { LoadingButton } from '../layout/LoadingButton';
import { backdropMotionVariants, dialogMotionVariants, overlayExitDurationMs } from '../lib/motion';
import {
  knowledgeUploadAccept,
  knowledgeUploadStatusLabel,
} from '../lib/knowledgeUploadValidation';
import { deleteKnowledgeDocument, knowledgeBackendLabel, listKnowledgeDocuments } from '../services/knowledge';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { useKnowledgeUploadQueue } from './useKnowledgeUploadQueue';

type Props = {
  open: boolean;
  documents: KnowledgeDocument[];
  qualityMode?: QualityMode;
  onDocumentsChange: (documents: KnowledgeDocument[]) => void;
  onDeleted?: (docId: string) => void;
  onOpenChange: (open: boolean) => void;
  projectId: string;
};

export function KnowledgeBaseManagerDialog({ open, documents, qualityMode = 'balanced', onDocumentsChange, onDeleted, onOpenChange, projectId }: Props) {
  const [dragging, setDragging] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<KnowledgeDocument | null>(null);
  const [scheduledDelete, setScheduledDelete] = useState<KnowledgeDocument | null>(null);
  const [deletingId, setDeletingId] = useState('');
  const deleteTimerRef = useRef<number | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const closeDialog = () => onOpenChange(false);
  const refresh = async () => onDocumentsChange(await listKnowledgeDocuments(projectId));
  const uploads = useKnowledgeUploadQueue({ onDocumentsChanged: refresh, projectId });
  const busy = uploads.busy || Boolean(deletingId);
  const dialogRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.dialog,
    onClose: closeDialog,
    open,
    suspended: Boolean(pendingDelete),
  });

  useEffect(() => {
    if (!open) return;
    void refresh().catch((error) => uploads.setMessage(error instanceof Error ? error.message : '资料列表刷新失败。'));
  }, [open, projectId]);

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragging(false);
    uploads.enqueue(event.dataTransfer.files);
  };

  const removeNow = async (doc: KnowledgeDocument) => {
    setScheduledDelete(null);
    setDeletingId(doc.doc_id);
    uploads.setMessage(`正在删除 ${doc.title} 并同步索引...`);
    try {
      const result = await deleteKnowledgeDocument(doc.doc_id, projectId);
      onDeleted?.(doc.doc_id);
      await refresh();
      uploads.setMessage(result.message || `已删除 ${result.deleted_chunks ?? doc.chunk_count} 个片段。`);
    } catch (error) {
      uploads.setMessage(error instanceof Error ? `删除失败：${error.message}` : '删除失败');
    } finally {
      setPendingDelete(null);
      setDeletingId('');
    }
  };

  const scheduleRemove = (doc: KnowledgeDocument) => {
    setPendingDelete(null);
    setScheduledDelete(doc);
    uploads.setMessage(`“${doc.title}”将在 5 秒后从知识库删除。`);
    if (deleteTimerRef.current) window.clearTimeout(deleteTimerRef.current);
    deleteTimerRef.current = window.setTimeout(() => {
      deleteTimerRef.current = null;
      void removeNow(doc);
    }, 5000);
  };

  const undoRemove = () => {
    if (deleteTimerRef.current) window.clearTimeout(deleteTimerRef.current);
    deleteTimerRef.current = null;
    setScheduledDelete(null);
    uploads.setMessage('已取消删除，资料保持不变。');
  };

  useEffect(() => () => {
    if (deleteTimerRef.current) window.clearTimeout(deleteTimerRef.current);
  }, []);

  const dialog = (
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className={`knowledge-manager-backdrop app-overlay-backdrop mode-${qualityMode}`}
          exit="exit"
          initial="initial"
          onClick={(event) => {
            if (event.currentTarget === event.target) closeDialog();
          }}
          onPointerDown={(event) => {
            if (event.currentTarget === event.target) closeDialog();
          }}
          role="presentation"
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            aria-busy={busy}
            aria-label="知识库配置"
            aria-modal="true"
            className="knowledge-manager-dialog app-dialog-surface"
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            ref={dialogRef}
            role="dialog"
            tabIndex={-1}
            variants={dialogMotionVariants}
          >
            <div className="knowledge-manager-head">
              <div>
                <p className="eyebrow">项目资料</p>
                <h2><DatabaseZap size={18} />知识库配置</h2>
              </div>
              <button aria-label="关闭知识库配置" className="icon-button tech-icon-button" onClick={closeDialog} title={uploads.busy ? '关闭后上传仍会继续' : '关闭'}><X size={16} /></button>
            </div>

            <div className="knowledge-manager-summary">
              <strong>{documents.length}<span>资料文档</span></strong>
              <strong>{documents.reduce((sum, item) => sum + item.chunk_count, 0)}<span>检索片段</span></strong>
              <strong>{knowledgeBackendLabel(documents)}<span>索引后端</span></strong>
            </div>

            <input accept={knowledgeUploadAccept} disabled={busy} hidden multiple onChange={(event) => { uploads.enqueue(event.target.files); event.target.value = ''; }} ref={fileRef} type="file" />
            <section
              className={`knowledge-dropzone ${dragging ? 'dragging' : ''}`}
              onDragEnter={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                if (event.currentTarget === event.target) setDragging(false);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
            >
              <UploadCloud size={24} />
              <div>
                <strong>拖拽资料到这里，或批量选择文件</strong>
                <span>支持 TXT / MD / HTML / PDF / DOCX / EPUB，单文件 ≤ 20MB，一次最多 10 个。</span>
              </div>
              <LoadingButton className="tech-button knowledge-upload-cta" disabled={busy} loading={uploads.busy} loadingLabel="正在入库" onClick={() => fileRef.current?.click()}>
                <UploadCloud size={15} />选择文件
              </LoadingButton>
            </section>
            <div className={`knowledge-upload-queue ${uploads.queue.length ? '' : 'empty'}`}>
              {uploads.queue.map((item) => (
                <div className={item.status} key={item.id}>
                  <span><b>{item.name}</b><em>{knowledgeUploadStatusLabel(item.status)} · {item.message}</em></span>
                  {item.status === 'failed' ? <button className="ghost tiny-action" disabled={uploads.busy} onClick={() => uploads.retry(item.id)} type="button">重试</button> : null}
                </div>
              ))}
            </div>
            <p className="knowledge-manager-note">资料属于当前项目私有知识库。只有本次明确选中的文档会在前置规划中检索；命中内容保留来源，只作为创作参考。</p>

            <div className="knowledge-manager-list">
              {documents.length ? documents.map((doc) => (
                <article className={scheduledDelete?.doc_id === doc.doc_id ? 'pending-delete' : ''} key={doc.doc_id}>
                  <FileText size={15} />
                  <div>
                    <strong>{doc.title}</strong>
                    <span>{doc.chunk_count} 个内容片段 · 已建立语义索引</span>
                    <p>{doc.preview || doc.capability_note || '暂无预览'}</p>
                  </div>
                  <button aria-label={`删除资料 ${doc.title}`} className="danger-icon-button" disabled={busy || Boolean(scheduledDelete)} onClick={() => setPendingDelete(doc)} title="删除并同步索引" type="button">
                    <Trash2 size={14} />
                  </button>
                </article>
              )) : (
                <div className="knowledge-empty app-empty-state" role="status">
                  <DatabaseZap size={22} />
                  <strong>还没有项目资料</strong>
                  <span>上传 TXT/MD/HTML 可直接解析；PDF/DOCX 等格式会在 Docling 可用时增强解析。</span>
                </div>
              )}
            </div>

            <div className="knowledge-manager-feedback">
              {scheduledDelete ? (
                <div className="knowledge-delete-undo" role="status">
                  <span>“{scheduledDelete.title}”等待删除，5 秒内可撤销。</span>
                  <button className="ghost tiny-action" onClick={undoRemove} type="button">撤销删除</button>
                </div>
              ) : null}
              {uploads.message ? (
                <p
                  aria-live={isErrorMessage(uploads.message) ? 'assertive' : 'polite'}
                  className={`knowledge-manager-message ${isErrorMessage(uploads.message) ? 'app-error-state error' : ''}`}
                  role={isErrorMessage(uploads.message) ? 'alert' : 'status'}
                >
                  {uploads.message}
                </p>
              ) : null}
            </div>
          </motion.section>
          <DangerConfirmationDialog
            busy={busy}
            busyLabel="正在删除"
            confirmLabel="确认删除"
            description={`将从项目知识库移除“${pendingDelete?.title ?? ''}”及其索引片段，并清除工作流对这份资料的选择。`}
            details={[
              `索引片段：${pendingDelete?.chunk_count ?? 0} 个`,
              '已生成的运行快照、历史产物和交付版本不会被改写。',
              '确认后 5 秒内可撤销，超时后才会真正删除。',
            ]}
            modeClass={`mode-${qualityMode}`}
            onCancel={() => setPendingDelete(null)}
            onConfirm={() => {
              if (pendingDelete) scheduleRemove(pendingDelete);
            }}
            open={Boolean(pendingDelete)}
            title={`删除“${pendingDelete?.title ?? ''}”？`}
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  return createPortal(dialog, document.body);
}

function isErrorMessage(message: string) {
  return /失败|没有可上传|不支持|超过/.test(message);
}
