import { useEffect, useRef, useState, type DragEvent } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { DatabaseZap, FileText, Trash2, UploadCloud, X } from 'lucide-react';
import type { KnowledgeDocument } from '../contracts';
import { deleteKnowledgeDocument, knowledgeBackendLabel, listKnowledgeDocuments, uploadKnowledgeFile } from '../services/knowledge';

type Props = {
  open: boolean;
  documents: KnowledgeDocument[];
  onDocumentsChange: (documents: KnowledgeDocument[]) => void;
  onDeleted?: (docId: string) => void;
  onOpenChange: (open: boolean) => void;
};

type UploadQueueItem = {
  id: string;
  name: string;
  status: 'waiting' | 'uploading' | 'done' | 'failed' | 'rejected';
  message: string;
};

const allowedExtensions = ['.txt', '.md', '.markdown', '.html', '.htm', '.pdf', '.docx', '.epub'];
const maxFileSize = 20 * 1024 * 1024;
const maxBatchCount = 10;

export function KnowledgeBaseManagerDialog({ open, documents, onDocumentsChange, onDeleted, onOpenChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState('');
  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open]);

  const refresh = async () => {
    onDocumentsChange(await listKnowledgeDocuments());
  };

  const upload = async (files: FileList | File[] | null) => {
    const selected = Array.from(files ?? []);
    if (!selected.length) return;
    const { valid, queueItems } = validateFiles(selected);
    setQueue(queueItems);
    if (!valid.length) {
      setMessage('没有可上传的有效文件，请检查格式、大小和数量限制。');
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    setBusy(true);
    setMessage(`正在处理 ${valid.length} 个文件，解析、分块并写入知识库索引...`);
    try {
      let successCount = 0;
      for (const file of valid) {
        setQueue((items) => items.map((item) => (item.id === queueId(file) ? { ...item, status: 'uploading', message: '上传中' } : item)));
        try {
          const payload = await uploadKnowledgeFile(file);
          successCount += 1;
          setQueue((items) => items.map((item) => (
            item.id === queueId(file)
              ? { ...item, status: 'done', message: `${payload.document.chunk_count} 个片段` }
              : item
          )));
        } catch (error) {
          setQueue((items) => items.map((item) => (
            item.id === queueId(file)
              ? { ...item, status: 'failed', message: error instanceof Error ? error.message : '上传失败' }
              : item
          )));
        }
      }
      await refresh();
      setMessage(successCount ? `已入库 ${successCount} 个文件。` : '上传失败，请查看队列状态。');
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files);
  };

  const remove = async (doc: KnowledgeDocument) => {
    setBusy(true);
    setMessage(`正在删除 ${doc.title} 并同步索引...`);
    try {
      const result = await deleteKnowledgeDocument(doc.doc_id);
      onDeleted?.(doc.doc_id);
      await refresh();
      setMessage(result.message || `已删除 ${result.deleted_chunks ?? doc.chunk_count} 个片段。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '删除失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open ? (
        <div className="knowledge-manager-backdrop" role="presentation">
          <motion.section
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="knowledge-manager-dialog"
            exit={{ opacity: 0, scale: 0.98, y: 8 }}
            initial={{ opacity: 0, scale: 0.98, y: 8 }}
            transition={{ duration: 0.18 }}
          >
            <div className="knowledge-manager-head">
              <div>
                <p className="eyebrow">Project Knowledge Base</p>
                <h2><DatabaseZap size={18} />知识库配置</h2>
              </div>
              <button className="icon-button tech-icon-button" onClick={() => onOpenChange(false)} title="关闭"><X size={16} /></button>
            </div>

            <div className="knowledge-manager-summary">
              <strong>{documents.length}<span>资料文档</span></strong>
              <strong>{documents.reduce((sum, item) => sum + item.chunk_count, 0)}<span>检索片段</span></strong>
              <strong>{knowledgeBackendLabel(documents)}<span>索引后端</span></strong>
            </div>

            <input accept={allowedExtensions.join(',')} hidden multiple onChange={(event) => void upload(event.target.files)} ref={fileRef} type="file" />
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
              <button className="tech-button knowledge-upload-cta" disabled={busy} onClick={() => fileRef.current?.click()} type="button">
                <UploadCloud size={15} />{busy ? '处理中' : '选择文件'}
              </button>
            </section>
            {queue.length ? (
              <div className="knowledge-upload-queue">
                {queue.map((item) => (
                  <span className={item.status} key={item.id}>
                    <b>{item.name}</b>
                    <em>{statusLabel(item.status)} · {item.message}</em>
                  </span>
                ))}
              </div>
            ) : null}
            <p className="knowledge-manager-note">资料属于当前项目私有知识库。智能联网搜索开启时会同时检索这里的资料，联网内容优先，知识库命中作为补充约束。</p>

            <div className="knowledge-manager-list">
              {documents.length ? documents.map((doc) => (
                <article key={doc.doc_id}>
                  <FileText size={15} />
                  <div>
                    <strong>{doc.title}</strong>
                    <span>{doc.chunk_count} chunks · {doc.parser} · {doc.backend || 'local-hybrid'}</span>
                    <p>{doc.preview || doc.capability_note || '暂无预览'}</p>
                  </div>
                  <button className="danger-icon-button" disabled={busy} onClick={() => void remove(doc)} title="删除并同步索引" type="button">
                    <Trash2 size={14} />
                  </button>
                </article>
              )) : (
                <div className="knowledge-empty">
                  <DatabaseZap size={22} />
                  <strong>还没有项目资料</strong>
                  <span>上传 TXT/MD/HTML 可直接解析；PDF/DOCX 等格式会在 Docling 可用时增强解析。</span>
                </div>
              )}
            </div>

            {message ? <p className="knowledge-manager-message">{message}</p> : null}
          </motion.section>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

function validateFiles(files: File[]) {
  const overflow = files.length > maxBatchCount;
  const allowed = files.slice(0, maxBatchCount);
  const valid: File[] = [];
  const queueItems: UploadQueueItem[] = allowed.map((file) => {
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
    if (!allowedExtensions.includes(extension)) {
      return { id: queueId(file), name: file.name, status: 'rejected', message: '格式不支持' };
    }
    if (file.size > maxFileSize) {
      return { id: queueId(file), name: file.name, status: 'rejected', message: '超过 20MB' };
    }
    valid.push(file);
    return { id: queueId(file), name: file.name, status: 'waiting', message: '等待上传' };
  });
  if (overflow) {
    queueItems.push({
      id: `overflow-${Date.now()}`,
      name: `其余 ${files.length - maxBatchCount} 个文件`,
      status: 'rejected',
      message: '一次最多上传 10 个文件',
    });
  }
  return { valid, queueItems };
}

function queueId(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

function statusLabel(status: UploadQueueItem['status']) {
  if (status === 'waiting') return '等待';
  if (status === 'uploading') return '上传中';
  if (status === 'done') return '完成';
  if (status === 'failed') return '失败';
  return '已跳过';
}
