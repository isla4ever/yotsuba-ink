import type {
  KnowledgeDeleteResponse,
  KnowledgeDocument,
  KnowledgeUploadPhase,
  KnowledgeUploadResponse,
} from '../contracts';

const legacyDemoKnowledgeStorageKey = 'novel-workflow-demo-knowledge-documents';
const demoKnowledgeStorageKeyPrefix = 'novel-workflow-demo-knowledge-documents:';

export async function listKnowledgeDocuments(projectId = 'default'): Promise<KnowledgeDocument[]> {
  try {
    const response = await fetch(`/api/knowledge/documents?project_id=${encodeURIComponent(projectId)}`);
    if (!response.ok) throw await knowledgeApiError(response, '/api/knowledge/documents');
    const documents = await response.json() as KnowledgeDocument[];
    return [...documents, ...loadStoredDemoDocuments(projectId)].filter(uniqueDocument);
  } catch (error) {
    if (!isServiceUnavailable(error)) throw error;
    return loadDemoDocuments(projectId);
  }
}

export async function uploadKnowledgeFile(
  file: File,
  projectId = 'default',
  onPhase?: (phase: KnowledgeUploadPhase) => void,
): Promise<KnowledgeUploadResponse> {
  onPhase?.('reading');
  const content = await fileToBase64(file);
  onPhase?.('indexing');
  try {
    return await postJson<KnowledgeUploadResponse>('/api/knowledge/documents/upload', {
      title: file.name.replace(/\.[^.]+$/, ''),
      content,
      filename: file.name,
      content_type: file.type || 'application/octet-stream',
      project_id: projectId,
      encoding: 'base64',
    });
  } catch (error) {
    if (!isServiceUnavailable(error)) throw error;
    return createDemoUpload(file, content, projectId);
  }
}

export async function deleteKnowledgeDocument(docId: string, backend?: string, projectId = 'default'): Promise<KnowledgeDeleteResponse> {
  if (backend === 'frontend-demo' || loadStoredDemoDocuments(projectId).some((document) => document.doc_id === docId)) {
    const documents = loadStoredDemoDocuments(projectId).filter((document) => document.doc_id !== docId);
    saveDemoDocuments(projectId, documents);
    return {
      ok: true,
      doc_id: docId,
      deleted_chunks: 0,
      backend: 'frontend-demo',
      backend_synced: false,
      message: '已从本机演示资料中移除；真实索引未受影响。',
    };
  }
  const response = await fetch(`/api/knowledge/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' });
  if (!response.ok) throw await knowledgeApiError(response, `/api/knowledge/documents/${docId}`);
  return response.json() as Promise<KnowledgeDeleteResponse>;
}

export function knowledgeBackendLabel(documents: KnowledgeDocument[]) {
  const backends = new Set(documents.map((item) => item.backend).filter(Boolean));
  if (!backends.size) return '等待资料';
  if (backends.size > 1) return '混合来源';
  const backend = [...backends][0];
  if (backend === 'redis-hybrid') return 'Redis Hybrid';
  if (backend === 'redis-unavailable') return 'Redis 待同步';
  if (backend === 'frontend-demo') return '本机演示';
  return '本地 Hybrid';
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await knowledgeApiError(response, url);
  return response.json() as Promise<T>;
}

async function knowledgeApiError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    // Preserve the HTTP status when an upstream proxy does not return JSON.
  }
  return new KnowledgeApiError(detail || `知识库请求失败：${url} (${response.status})`, response.status);
}

function isServiceUnavailable(error: unknown) {
  return error instanceof TypeError
    || error instanceof KnowledgeApiError && [502, 503, 504].includes(error.status);
}

class KnowledgeApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'KnowledgeApiError';
  }
}

function createDemoUpload(file: File, content: string, projectId: string): KnowledgeUploadResponse {
  const document: KnowledgeDocument = {
    doc_id: `demo-doc-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    project_id: projectId,
    title: file.name.replace(/\.[^.]+$/, ''),
    filename: file.name,
    content_type: file.type || 'application/octet-stream',
    char_count: Math.round(content.length * 0.75),
    chunk_count: Math.max(1, Math.ceil(content.length / 2400)),
    status: 'ready',
    parser: 'frontend-demo',
    backend: 'frontend-demo',
    capability_note: '本机服务不可用，已保存为本机演示资料；未建立真实语义索引。',
    preview: `${file.name} 已保留在当前浏览器的演示资料中。`,
    created_at: new Date().toISOString(),
  };
  saveDemoDocuments(projectId, [document, ...loadStoredDemoDocuments(projectId)]);
  return { document };
}

function loadDemoDocuments(projectId: string): KnowledgeDocument[] {
  try {
    if (hasStoredDemoDocuments(projectId)) return loadStoredDemoDocuments(projectId);
  } catch {
    // Fall through to a visible seeded demo when browser storage is unavailable.
  }
  return seededDemoDocuments(projectId);
}

function loadStoredDemoDocuments(projectId: string): KnowledgeDocument[] {
  try {
    const stored = window.localStorage.getItem(demoStorageKey(projectId))
      ?? (projectId === 'default' ? window.localStorage.getItem(legacyDemoKnowledgeStorageKey) : null);
    const parsed = stored ? JSON.parse(stored) : null;
    if (Array.isArray(parsed)) {
      return parsed.filter((doc) => !doc.project_id || doc.project_id === projectId);
    }
  } catch {
    // Local demo documents are optional and must not block the real API.
  }
  return [];
}

function saveDemoDocuments(projectId: string, documents: KnowledgeDocument[]) {
  try {
    window.localStorage.setItem(demoStorageKey(projectId), JSON.stringify(documents.slice(0, 20)));
  } catch {
    // The upload response still communicates that browser persistence failed later.
  }
}

function seededDemoDocuments(projectId: string): KnowledgeDocument[] {
  if (projectId !== 'default') return [];
  return [{
    doc_id: 'demo-brief-mist-harbor',
    project_id: projectId,
    title: '雾港旧声投稿项 Brief',
    filename: 'mist-harbor-brief.md',
    content_type: 'text/markdown',
    char_count: 1620,
    chunk_count: 5,
    status: 'ready',
    parser: 'frontend-demo',
    backend: 'frontend-demo',
    capability_note: '本机服务不可用时显示的本机演示资料，未连接真实知识库。',
    preview: '旧港、声纹档案、蓝潮禁区、三章投稿项结构。',
    created_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
  }];
}

function hasStoredDemoDocuments(projectId: string) {
  return window.localStorage.getItem(demoStorageKey(projectId)) !== null
    || projectId === 'default' && window.localStorage.getItem(legacyDemoKnowledgeStorageKey) !== null;
}

function demoStorageKey(projectId: string) {
  return `${demoKnowledgeStorageKeyPrefix}${projectId}`;
}

function uniqueDocument(document: KnowledgeDocument, index: number, documents: KnowledgeDocument[]) {
  return documents.findIndex((item) => item.doc_id === document.doc_id) === index;
}

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
    reader.readAsDataURL(file);
  });
}
