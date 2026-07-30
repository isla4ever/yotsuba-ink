import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  downloadRunExportReceipt,
  listRunExports,
  listRunHistory,
  restoreRunSnapshot,
} from './runHistoryApi';

describe('run history API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('loads compact server history without injecting demo runs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{
        run_id: 'run-1',
        title: '服务端小说',
        status: 'paused',
        current_stage: { id: 'text', label: '正文生成', type: 'chapter_text' },
        can_resume: true,
      }],
      next_cursor: 'next',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const history = await listRunHistory({ limit: 12 });

    expect(history.items).toHaveLength(1);
    expect(history.items[0]).toMatchObject({ run_id: 'run-1', title: '服务端小说', source: 'server' });
    expect(history.next_cursor).toBe('next');
  });

  it('restores a snapshot with request id and expected revision', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      run_id: 'run-1', snapshot_id: 'snapshot-1', status: 'restored_paused', state_revision: 4,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    await restoreRunSnapshot('run-1', {
      snapshot_id: 'snapshot-1',
      request_id: 'restore-request-1',
      expected_revision: 3,
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/restore-snapshot', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ snapshot_id: 'snapshot-1', request_id: 'restore-request-1', expected_revision: 3 }),
    }));
  });

  it('redownloads a stored export receipt with its UTF-8 filename', async () => {
    const sha256 = 'ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73';
    const fetchMock = vi.fn().mockResolvedValue(new Response('content', {
      status: 200,
      headers: {
        'Content-Disposition': "attachment; filename=novel-export.md; filename*=UTF-8''%E9%9B%BE%E6%B8%AF.md",
        'X-Export-Sha256': sha256,
      },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();

    const downloaded = await downloadRunExportReceipt('run-1', 'export-1', {
      expectedSha256: sha256,
      expectedSizeBytes: 7,
      signal: controller.signal,
    });

    expect(downloaded.filename).toBe('雾港.md');
    expect(await downloaded.blob.text()).toBe('content');
    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run-1/exports/export-1', { signal: controller.signal });
  });

  it('blocks a stored export when the immutable response digest header is missing', async () => {
    const sha256 = 'ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('content', { status: 200 })));

    await expect(downloadRunExportReceipt('run-1', 'export-1', {
      expectedSha256: sha256,
      expectedSizeBytes: 7,
    })).rejects.toThrow('响应缺少 SHA-256');
  });

  it('normalizes stored export receipts for stage recovery', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{
        export_id: 'export-1',
        run_id: 'run-1',
        request_id: 'request-1',
        version: 2,
        selection_digest: 'a'.repeat(64),
        format: 'zip',
        chapter_ids: ['chapter-2', 'chapter-1'],
        metadata: { title: '雾港', bundle_name: '雾港终稿' },
        filename: '雾港终稿.zip',
        cover_asset: { candidate_id: 'cover-1', asset_id: 'cover-abc', sha256: 'b'.repeat(64) },
        files: [{ path: '雾港终稿.zip', scope: 'package', size_bytes: 120, sha256: 'c'.repeat(64) }],
      }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const receipts = await listRunExports('run-1');

    expect(receipts[0]).toMatchObject({
      format: 'zip',
      version: 2,
      selection_digest: 'a'.repeat(64),
      chapter_ids: ['chapter-2', 'chapter-1'],
      metadata: { title: '雾港', author: '', bundle_name: '雾港终稿', version_note: '' },
      filename: '雾港终稿.zip',
      cover_asset: { candidate_id: 'cover-1', asset_id: 'cover-abc' },
      files: [{ path: '雾港终稿.zip', scope: 'package', size_bytes: 120 }],
    });
  });
});
