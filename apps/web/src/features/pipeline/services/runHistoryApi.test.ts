import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  downloadRunExportReceipt,
  listRunExports,
  listRunHistory,
} from './runHistoryApi';

describe('run history API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('loads compact server history without injecting demo runs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{
        run_id: 'run-1',
        project_id: 'project-1',
        title: '服务端小说',
        quality_mode: 'balanced',
        status: 'awaiting_decision',
        current_stage: { id: 'text', label: '正文', type: 'text' },
        completed_stage_ids: ['info', 'characters', 'summary', 'outline', 'detail'],
        created_at: '2026-08-11T00:00:00Z',
        updated_at: '2026-08-11T00:01:00Z',
        completed_at: '',
        words: 1200,
        total_tokens: 800,
        estimated_cost_usd: 0.02,
        summary: 'LangGraph 运行读模型',
        can_branch: true,
        checkpoint_id: 'checkpoint-1',
        export_ready: false,
        export_count: 0,
        latest_export: null,
      }],
      next_cursor: 'next',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const history = await listRunHistory({ limit: 12 });

    expect(history.items).toHaveLength(1);
    expect(history.items[0]).toMatchObject({
      run_id: 'run-1',
      title: '服务端小说',
      status: 'awaiting_decision',
      can_branch: true,
      checkpoint_id: 'checkpoint-1',
      source: 'server',
    });
    expect(history.next_cursor).toBe('next');
  });

  it('rejects a legacy history item instead of injecting vNext defaults', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{ run_id: 'legacy-run', status: 'paused' }],
      next_cursor: '',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    await expect(listRunHistory()).rejects.toThrow('vNext contract');
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

  it('accepts only the vNext immutable export receipt', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{
        export_id: 'export-1',
        run_id: 'run-1',
        artifact_id: 'export-committed-1',
        artifact_signature: 'a'.repeat(64),
        format: 'zip',
        chapter_version_ids: ['chapter-2-v1-accepted', 'chapter-1-v1-accepted'],
        cover_asset_id: 'cover-abc',
        metadata: { title: '雾港', author: '', version_note: '终稿' },
        filename: '雾港终稿.zip',
        media_type: 'application/zip',
        size_bytes: 120,
        sha256: 'c'.repeat(64),
        created_at: '2026-08-11T00:00:00Z',
      }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const receipts = await listRunExports('run-1');

    expect(receipts[0]).toMatchObject({
      format: 'zip',
      artifact_id: 'export-committed-1',
      artifact_signature: 'a'.repeat(64),
      chapter_version_ids: ['chapter-2-v1-accepted', 'chapter-1-v1-accepted'],
      metadata: { title: '雾港', author: '', version_note: '终稿' },
      filename: '雾港终稿.zip',
      cover_asset_id: 'cover-abc',
      media_type: 'application/zip',
      size_bytes: 120,
    });
  });
});
