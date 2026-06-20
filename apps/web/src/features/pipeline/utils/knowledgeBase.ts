import type { KnowledgeDeleteResponse, KnowledgeDocument } from '../types/workflow';

export async function listKnowledgeDocuments(projectId = 'default'): Promise<KnowledgeDocument[]> {
  const response = await fetch(`/api/knowledge/documents?project_id=${encodeURIComponent(projectId)}`);
  if (!response.ok) return [];
  return response.json();
}

export async function uploadKnowledgeFile(file: File, projectId = 'default') {
  const content = await fileToBase64(file);
  const response = await fetch('/api/knowledge/documents/upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: file.name.replace(/\.[^.]+$/, ''),
      filename: file.name,
      content_type: file.type || 'application/octet-stream',
      content,
      encoding: 'base64',
      project_id: projectId,
    }),
  });
  if (!response.ok) throw new Error('知识库文件上传失败');
  return response.json();
}

export async function deleteKnowledgeDocument(docId: string): Promise<KnowledgeDeleteResponse> {
  const response = await fetch(`/api/knowledge/documents/${docId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('知识库文档删除失败');
  return response.json();
}

export function knowledgeBackendLabel(documents: KnowledgeDocument[]) {
  const backend = documents.find((item) => item.backend)?.backend;
  if (!backend) return '等待资料';
  if (backend === 'redis-hybrid') return 'Redis Hybrid';
  if (backend === 'redis-unavailable') return 'Redis 待同步';
  return '本地 Hybrid';
}

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
    reader.readAsDataURL(file);
  });
}
