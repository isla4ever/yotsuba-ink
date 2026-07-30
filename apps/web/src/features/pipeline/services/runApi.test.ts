import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  applyChapterSelectionRevision,
  approveRunArtifact,
  decideChapterWritebackProposal,
  downloadRunExportPreview,
  downloadRunExportPackage,
  getRun,
  isRunNotFoundError,
  regenerateRunDraft,
  RunApiError,
  syncChapterSummary,
} from './runApi';

describe('run snapshot API', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('preserves a 404 so recovery can discard a stale local run', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 404 })));

    const error = await getRun('missing-run').catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(RunApiError);
    expect(isRunNotFoundError(error)).toBe(true);
  });

  it('does not classify a transport failure as a missing run', async () => {
    const error = new TypeError('network unavailable');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(error));

    const received = await getRun('cached-run').catch((reason: unknown) => reason);

    expect(received).toBe(error);
    expect(isRunNotFoundError(received)).toBe(false);
  });

  it('keeps the backend validation detail on mutation failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'characters.0.relations: Field required' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    const error = await regenerateRunDraft('run-1', 'workflow-1', 'info', '强化关系', 3)
      .catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(RunApiError);
    expect((error as Error).message).toContain('characters.0.relations');
  });

  it('submits the current edited artifact to the stage approval endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const editedArtifact = { full_synopsis: '人工编辑后的完整梗概' };

    await approveRunArtifact('run-1', 'summary', 'summary', editedArtifact);

    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/approve-artifact', expect.objectContaining({
      body: JSON.stringify({
        node_id: 'summary',
        output_key: 'summary',
        artifact: editedArtifact,
      }),
    }));
  });

  it('accepts a selection candidate through the dedicated chapter endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ artifact: {}, chapter: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await applyChapterSelectionRevision('run-1', {
      workflow_id: 'workflow-1',
      node_id: 'text',
      request_id: 'revision-request-1',
      candidate_signature: 'a'.repeat(64),
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/chapter-selection-revisions/apply', expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('revision-request-1'),
    }));
  });

  it('syncs a chapter summary through the versioned review endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ artifact: {}, chapter: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await syncChapterSummary('run-1', 'chapter-1', {
      workflow_id: 'workflow-1',
      node_id: 'text',
      chapter_id: 'chapter-1',
      summary: '同步后的章节摘要',
      base_version: 2,
      base_signature: 'a'.repeat(64),
      persisted_signature: 'b'.repeat(64),
      base_chapter: { id: 'chapter-1' },
      request_id: 'summary-sync-request-1',
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/chapters/chapter-1/sync-summary', expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('summary-sync-request-1'),
    }));
  });

  it('sends explicit Canon conflict resolutions with proposal decisions', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ artifact: {}, chapter: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await decideChapterWritebackProposal('run-1', 'chapter-1', {
      workflow_id: 'workflow-1',
      node_id: 'text',
      chapter_id: 'chapter-1',
      proposal_id: 'proposal-1',
      proposal_signature: 'a'.repeat(64),
      decision: 'accepted',
      base_version: 2,
      base_signature: 'b'.repeat(64),
      request_id: 'proposal-request-1',
      conflict_resolutions: { 'canon-conflict-1': 'keep_existing' },
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/chapters/chapter-1/writeback-proposal', expect.objectContaining({
      body: expect.stringContaining('canon-conflict-1'),
    }));
  });

  it('downloads an export package and decodes the UTF-8 filename', async () => {
    const content = 'PK\u0003\u0004';
    const sha256 = '8dcc7e601606217f3b754766511182a916b17e9a26a94c9d887104eba92e9bb2';
    const fetchMock = vi.fn().mockResolvedValue(new Response(content, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': "attachment; filename=novel-export.zip; filename*=UTF-8''%E9%9B%BE%E6%B8%AF.zip",
        'X-Export-Id': 'export-1',
        'X-Export-Version': '3',
        'X-Source-Snapshot-Id': 'snapshot-1',
        'X-Artifact-Signature': 'artifact-signature-1',
        'X-Selection-Digest': 'selection-digest-1',
        'X-Export-Sha256': sha256,
      },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const metadata = { title: '雾港', author: '林舟', bundle_name: '雾港投稿版', version_note: '编辑定稿版' };

    const result = await downloadRunExportPackage('run-1', 'zip', ['chapter-1'], 'request-1', metadata);

    expect(result).toMatchObject({
      filename: '雾港.zip',
      export_id: 'export-1',
      version: 3,
      snapshot_id: 'snapshot-1',
      artifact_signature: 'artifact-signature-1',
      selection_digest: 'selection-digest-1',
      sha256,
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/export-package', expect.objectContaining({
      body: JSON.stringify({ format: 'zip', chapter_ids: ['chapter-1'], request_id: 'request-1', metadata }),
    }));
  });

  it('downloads a mutable preview without creating a final export receipt', async () => {
    const content = '# preview';
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(content));
    const sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
    const fetchMock = vi.fn().mockResolvedValue(new Response(content, {
      status: 200,
      headers: {
        'Content-Disposition': "attachment; filename=novel-preview.md; filename*=UTF-8''%E9%9B%BE%E6%B8%AF-preview.md",
        'X-Export-Mode': 'preview',
        'X-Preview-Sha256': sha256,
      },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const metadata = { title: '雾港', author: '', bundle_name: '雾港', version_note: '连载预览' };

    const result = await downloadRunExportPreview('run-1', 'md', ['chapter-1'], metadata);

    expect(result).toMatchObject({ filename: '雾港-preview.md', sha256 });
    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/export-preview', expect.objectContaining({
      body: JSON.stringify({ format: 'md', chapter_ids: ['chapter-1'], metadata }),
    }));
  });
});
