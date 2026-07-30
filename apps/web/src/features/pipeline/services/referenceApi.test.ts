import { afterEach, describe, expect, it, vi } from 'vitest';
import { searchKnowledgeReferences, searchWebReferences } from './referenceApi';

describe('reference API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends the real web search contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      enabled: true,
      provider: 'tavily',
      message: '',
      results: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    await searchWebReferences('悬疑 旧港', 4);

    expect(fetchMock).toHaveBeenCalledWith('/api/references/search', expect.objectContaining({
      body: JSON.stringify({ query: '悬疑 旧港', max_results: 4, search_depth: 'basic' }),
    }));
  });

  it('passes selected document ids to knowledge search', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      backend: 'local-hybrid', backend_available: true, query_rewrite: '', message: '', results: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    await searchKnowledgeReferences({ query: '记忆实验', intent: '只看设定', docIds: ['doc-a'], topK: 3 });

    expect(fetchMock).toHaveBeenCalledWith('/api/knowledge/search', expect.objectContaining({
      body: JSON.stringify({
        query: '记忆实验', intent: '只看设定', project_id: 'default', doc_ids: ['doc-a'], top_k: 3,
      }),
    }));
  });

  it('keeps backend validation details on failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'query is required' }),
      { status: 422, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(searchWebReferences('')).rejects.toThrow('query is required');
  });
});
