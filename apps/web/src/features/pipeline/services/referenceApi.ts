import type { KnowledgeSearchResponse, ReferenceSearchResponse } from '../contracts';

export async function searchWebReferences(query: string, maxResults = 5): Promise<ReferenceSearchResponse> {
  return postJson<ReferenceSearchResponse>('/api/references/search', {
    query,
    max_results: maxResults,
    search_depth: 'basic',
  });
}

export async function searchKnowledgeReferences(input: {
  query: string;
  intent?: string;
  projectId: string;
  docIds?: string[];
  topK?: number;
}): Promise<KnowledgeSearchResponse> {
  return postJson<KnowledgeSearchResponse>('/api/knowledge/search', {
    query: input.query,
    intent: input.intent ?? '',
    project_id: input.projectId,
    doc_ids: input.docIds ?? [],
    top_k: input.topK ?? 6,
  });
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await referenceApiError(response, url);
  return response.json() as Promise<T>;
}

async function referenceApiError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    // The status still provides a useful failure reason when the body is not JSON.
  }
  return new Error(detail || `请求失败：${url} (${response.status})`);
}
