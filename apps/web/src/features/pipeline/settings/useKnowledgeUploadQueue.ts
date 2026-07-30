import { useRef, useState } from 'react';
import {
  knowledgeQueueId,
  validateKnowledgeFiles,
  type KnowledgeUploadQueueItem,
} from '../lib/knowledgeUploadValidation';
import { uploadKnowledgeFile } from '../services/knowledge';

type Options = {
  onDocumentsChanged: () => Promise<void> | void;
  projectId: string;
};

export function useKnowledgeUploadQueue({ onDocumentsChanged, projectId }: Options) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [queue, setQueue] = useState<KnowledgeUploadQueueItem[]>([]);
  const activeRef = useRef(false);
  const filesRef = useRef(new Map<string, File>());
  const onDocumentsChangedRef = useRef(onDocumentsChanged);
  onDocumentsChangedRef.current = onDocumentsChanged;

  const updateItem = (id: string, update: Partial<KnowledgeUploadQueueItem>) => {
    setQueue((items) => items.map((item) => (item.id === id ? { ...item, ...update } : item)));
  };

  const processFiles = async (files: File[]) => {
    if (activeRef.current || !files.length) return;
    activeRef.current = true;
    setBusy(true);
    let successCount = 0;
    let demoCount = 0;
    try {
      for (const file of files) {
        const id = knowledgeQueueId(file);
        try {
          const payload = await uploadKnowledgeFile(file, projectId, (phase) => {
            updateItem(id, {
              status: phase,
              message: phase === 'reading' ? '正在读取并编码文件' : '正在解析、分块并建立索引',
            });
          });
          const demo = payload.document.backend === 'frontend-demo';
          successCount += demo ? 0 : 1;
          demoCount += demo ? 1 : 0;
          updateItem(id, {
            status: demo ? 'demo' : 'done',
            message: demo ? '本机服务不可用，未建立真实语义索引' : `${payload.document.chunk_count} 个片段已建立索引`,
          });
          filesRef.current.delete(id);
        } catch (error) {
          updateItem(id, { status: 'failed', message: errorMessage(error) });
        }
      }
      try {
        await onDocumentsChangedRef.current();
      } catch (error) {
        setMessage(`文件处理已结束，但资料列表刷新失败：${errorMessage(error)}`);
        return;
      }
      const parts = [];
      if (successCount) parts.push(`${successCount} 个文件已写入项目知识库`);
      if (demoCount) parts.push(`${demoCount} 个文件仅保存在本机演示资料中`);
      setMessage(parts.length ? `${parts.join('；')}。` : '上传失败，请查看队列并重试。');
    } finally {
      activeRef.current = false;
      setBusy(false);
    }
  };

  const enqueue = (files: FileList | File[] | null) => {
    if (activeRef.current) return;
    const selected = Array.from(files ?? []);
    if (!selected.length) return;
    const { valid, queueItems } = validateKnowledgeFiles(selected);
    setQueue(queueItems);
    filesRef.current.clear();
    valid.forEach((file) => filesRef.current.set(knowledgeQueueId(file), file));
    if (!valid.length) {
      setMessage('没有可上传的有效文件，请检查格式、大小和数量限制。');
      return;
    }
    setMessage(`已加入 ${valid.length} 个文件，将按顺序解析入库。`);
    void processFiles(valid);
  };

  const retry = (queueId: string) => {
    if (activeRef.current) return;
    const file = filesRef.current.get(queueId);
    if (!file) {
      setMessage('原始文件已不在当前会话中，请重新选择文件。');
      return;
    }
    updateItem(queueId, { status: 'waiting', message: '等待重新上传' });
    void processFiles([file]);
  };

  return { busy, enqueue, message, queue, retry, setMessage };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '上传失败，请稍后重试。';
}
