import '../../../styles/entry-settings.css';
import { useEffect, useRef, useState, type DragEvent } from 'react';
import { BookOpen, DatabaseZap, FileText, Layers3, ServerCog, Trash2, UploadCloud } from 'lucide-react';
import type { KnowledgeDocument, QualityMode } from '../contracts';
import { DangerConfirmationDialog } from '../layout/DangerConfirmationDialog';
import { LoadingButton } from '../layout/LoadingButton';
import {
  knowledgeUploadAccept,
  knowledgeUploadStatusLabel,
} from '../lib/knowledgeUploadValidation';
import { deleteKnowledgeDocument, knowledgeBackendLabel, listKnowledgeDocuments } from '../services/knowledge';
import { useKnowledgeUploadQueue } from './useKnowledgeUploadQueue';

type Props = {
  documents: KnowledgeDocument[];
  projectId: string;
  qualityMode?: QualityMode;
  onDeleted?: (docId: string) => void;
  onDocumentsChange: (documents: KnowledgeDocument[]) => void;
};

/**
 * Full-page knowledge library (was a portal dialog). Documents are the
 * project-private retrieval corpus: upload feeds the chunk index, delete
 * removes chunks and clears workflow selections that referenced the doc.
 */
export function KnowledgeLibraryPage({ documents, projectId, qualityMode = 'balanced', onDeleted, onDocumentsChange }: Props) {
  const [dragging, setDragging] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<KnowledgeDocument | null>(null);
  const [scheduledDelete, setScheduledDelete] = useState<KnowledgeDocument | null>(null);
  const [deletingId, setDeletingId] = useState('');
  const deleteTimerRef = useRef<number | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const refresh = async () => onDocumentsChange(await listKnowledgeDocuments(projectId));
  const uploads = useKnowledgeUploadQueue({ onDocumentsChanged: refresh, projectId });
  const busy = uploads.busy || Boolean(deletingId);
  const chunkTotal = documents.reduce((sum, item) => sum + item.chunk_count, 0);

  useEffect(() => {
    if (!projectId) return;
    void refresh().catch((error) => uploads.setMessage(error instanceof Error ? error.message : '资料列表刷新失败。'));
    // Refresh once per project entry; upload/delete flows refresh themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

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

  return (
    <section aria-busy={busy} aria-labelledby="knowledge-page-title" className="knowledge-page workspace-page">
      <header className="workspace-page-head">
        <div className="workspace-page-title">
          <p className="eyebrow">项目资料库</p>
          <h1 id="knowledge-page-title"><BookOpen size={20} />知识资料</h1>
          <span>资料属于当前项目的私有知识库；被选中的文档会在前置规划中检索，命中内容保留来源。</span>
        </div>
        <dl className="workspace-page-stats">
          <div><dt><FileText size={13} />资料文档</dt><dd>{documents.length}</dd></div>
          <div><dt><Layers3 size={13} />检索片段</dt><dd>{chunkTotal}</dd></div>
          <div><dt><ServerCog size={13} />索引后端</dt><dd>{knowledgeBackendLabel(documents)}</dd></div>
        </dl>
      </header>

      {!projectId ? (
        <div className="knowledge-empty app-empty-state knowledge-page-no-project" role="status">
          <DatabaseZap size={22} />
          <strong>尚未打开作品</strong>
          <span>知识资料按作品隔离。请先在作品工作室打开或创建一个作品，再上传项目资料。</span>
        </div>
      ) : (
      <div className="knowledge-page-layout">
        <div className="knowledge-page-intake">
          <input accept={knowledgeUploadAccept} disabled={busy} hidden multiple onChange={(event) => { uploads.enqueue(event.target.files); event.target.value = ''; }} ref={fileRef} type="file" />
          <section
            aria-label="上传资料"
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

          {uploads.queue.length ? (
            <div aria-label="上传队列" className="knowledge-upload-queue">
              {uploads.queue.map((item) => (
                <div className={item.status} key={item.id}>
                  <span><b>{item.name}</b><em>{knowledgeUploadStatusLabel(item.status)} · {item.message}</em></span>
                  {item.status === 'failed' ? <button className="ghost tiny-action" disabled={uploads.busy} onClick={() => uploads.retry(item.id)} type="button">重试</button> : null}
                </div>
              ))}
            </div>
          ) : null}

          <div className="knowledge-page-feedback" role="presentation">
            {scheduledDelete ? (
              <div className="knowledge-delete-undo" role="status">
                <span>“{scheduledDelete.title}”等待删除，5 秒内可撤销。</span>
                <button className="ghost tiny-action" onClick={undoRemove} type="button">撤销删除</button>
              </div>
            ) : null}
            {uploads.message ? (
              <p
                aria-live={isErrorMessage(uploads.message) ? 'assertive' : 'polite'}
                className={`knowledge-page-message ${isErrorMessage(uploads.message) ? 'app-error-state error' : ''}`}
                role={isErrorMessage(uploads.message) ? 'alert' : 'status'}
              >
                {uploads.message}
              </p>
            ) : null}
          </div>
        </div>

        <section aria-label="已入库资料" className="knowledge-page-list nw-reveal-scroll">
          <header className="knowledge-page-list-head">
            <strong>已入库资料</strong>
            <span>{documents.length ? `${documents.length} 份 · ${chunkTotal} 个片段` : '暂无资料'}</span>
          </header>
          {documents.length ? documents.map((doc) => (
            <article className={`knowledge-doc-row${scheduledDelete?.doc_id === doc.doc_id ? ' pending-delete' : ''}`} key={doc.doc_id}>
              <span aria-hidden="true" className="knowledge-doc-icon"><FileText size={16} /></span>
              <div className="knowledge-doc-copy">
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
        </section>
      </div>
      )}

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
    </section>
  );
}

function isErrorMessage(message: string) {
  return /失败|没有可上传|不支持|超过/.test(message);
}
