import { afterEach, describe, expect, it, vi } from 'vitest';
import { deleteKnowledgeDocument, listKnowledgeDocuments } from './knowledge';

describe('knowledge API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('loads service documents from the real endpoint', async () => {
    const document = {
      doc_id: 'doc-1', title: '设定集', filename: 'world.md', chunk_count: 4,
      status: 'indexed', parser: 'plain-text', backend: 'local-hybrid', preview: '世界规则',
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([document]), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const documents = await listKnowledgeDocuments();

    expect(documents).toEqual([document]);
    expect(fetchMock).toHaveBeenCalledWith('/api/knowledge/documents?project_id=default');
  });

  it('returns an explicitly labelled demo document when listing is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));

    const documents = await listKnowledgeDocuments();

    expect(documents[0]).toMatchObject({ backend: 'frontend-demo', parser: 'frontend-demo' });
    expect(documents[0].capability_note).toContain('未连接真实知识库');
  });

  it('does not inherit default or legacy demo documents into a new project', async () => {
    const localStorage = createLocalStorage();
    localStorage.setItem('novel-workflow-demo-knowledge-documents', JSON.stringify([
      { doc_id: 'legacy-doc', title: '旧港资料', backend: 'frontend-demo' },
    ]));
    vi.stubGlobal('window', { localStorage });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));

    await expect(listKnowledgeDocuments('project-new')).resolves.toEqual([]);
  });

  it('keeps offline demo documents isolated by project', async () => {
    const localStorage = createLocalStorage();
    localStorage.setItem('novel-workflow-demo-knowledge-documents:project-a', JSON.stringify([
      { doc_id: 'project-a-doc', project_id: 'project-a', title: 'A 作品资料', backend: 'frontend-demo' },
    ]));
    localStorage.setItem('novel-workflow-demo-knowledge-documents:project-b', JSON.stringify([
      { doc_id: 'project-b-doc', project_id: 'project-b', title: 'B 作品资料', backend: 'frontend-demo' },
    ]));
    vi.stubGlobal('window', { localStorage });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));

    await expect(listKnowledgeDocuments('project-a')).resolves.toEqual([
      expect.objectContaining({ doc_id: 'project-a-doc', project_id: 'project-a' }),
    ]);
    await expect(listKnowledgeDocuments('project-b')).resolves.toEqual([
      expect.objectContaining({ doc_id: 'project-b-doc', project_id: 'project-b' }),
    ]);
  });

  it('does not hide a backend list error behind demo data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'knowledge store is corrupted' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(listKnowledgeDocuments()).rejects.toThrow('knowledge store is corrupted');
  });

  it('does not report a server delete as successful when the API rejects it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'document is in use' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(deleteKnowledgeDocument('server-doc')).rejects.toThrow('document is in use');
  });
});

function createLocalStorage(): Storage {
  const values = new Map<string, string>();
  return {
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    get length() { return values.size; },
    removeItem: (key) => { values.delete(key); },
    setItem: (key, value) => { values.set(key, String(value)); },
  };
}
