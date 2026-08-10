export type KnowledgeUploadQueueItem = {
  id: string;
  name: string;
  status: 'waiting' | 'reading' | 'indexing' | 'done' | 'failed' | 'rejected';
  message: string;
};

const allowedExtensions = ['.txt', '.md', '.markdown', '.html', '.htm', '.pdf', '.docx', '.epub'];
const maxFileSize = 20 * 1024 * 1024;
const maxBatchCount = 10;

export const knowledgeUploadAccept = allowedExtensions.join(',');

export function validateKnowledgeFiles(files: File[]) {
  const overflow = files.length > maxBatchCount;
  const allowed = files.slice(0, maxBatchCount);
  const valid: File[] = [];
  const queueItems: KnowledgeUploadQueueItem[] = allowed.map((file) => {
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
    if (!allowedExtensions.includes(extension)) {
      return { id: knowledgeQueueId(file), name: file.name, status: 'rejected', message: '格式不支持' };
    }
    if (file.size > maxFileSize) {
      return { id: knowledgeQueueId(file), name: file.name, status: 'rejected', message: '超过 20MB' };
    }
    valid.push(file);
    return { id: knowledgeQueueId(file), name: file.name, status: 'waiting', message: '等待上传' };
  });
  if (overflow) {
    queueItems.push({
      id: `overflow-${Date.now()}`,
      name: `其余 ${files.length - maxBatchCount} 个文件`,
      status: 'rejected',
      message: '一次最多上传 10 个文件',
    });
  }
  return { queueItems, valid };
}

export function knowledgeQueueId(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

export function knowledgeUploadStatusLabel(status: KnowledgeUploadQueueItem['status']) {
  if (status === 'waiting') return '等待';
  if (status === 'reading') return '读取文件';
  if (status === 'indexing') return '解析索引';
  if (status === 'done') return '完成';
  if (status === 'failed') return '失败';
  return '已跳过';
}
