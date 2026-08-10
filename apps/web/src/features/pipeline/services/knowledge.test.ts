import { afterEach, describe, expect, it, vi } from 'vitest';
import { deleteKnowledgeDocument, listKnowledgeDocuments } from './knowledge';

describe('knowledge API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('loads service documents from the real endpoint', async () => {
    const document = {
      doc_id: 'doc-1', project_id: 'project-1', title: '设定集', filename: 'world.md', chunk_count: 4,
      status: 'indexed', parser: 'plain-text', backend: 'local-hybrid', preview: '世界规则',
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([document]), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const documents = await listKnowledgeDocuments('project-1');

    expect(documents).toEqual([document]);
    expect(fetchMock).toHaveBeenCalledWith('/api/knowledge/documents?project_id=project-1');
  });

  it('surfaces transport failure instead of creating demo documents', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));

    await expect(listKnowledgeDocuments('project-1')).rejects.toThrow('offline');
  });

  it('does not hide a backend list error behind demo data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'knowledge store is corrupted' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(listKnowledgeDocuments('project-1')).rejects.toThrow('knowledge store is corrupted');
  });

  it('does not report a server delete as successful when the API rejects it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'document is in use' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(deleteKnowledgeDocument('server-doc', 'project-1')).rejects.toThrow('document is in use');
  });
});
