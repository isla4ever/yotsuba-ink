import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createRunStream,
  getChapterVersion,
  getRun,
  isRunNotFoundError,
  resolveRunDecision,
  RunApiError,
} from './runApi';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { buildRunInputs } from '../state/runInputs';

describe('LangGraph run API', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('preserves a 404 so a stale local observer can be discarded', async () => {
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

  it('rejects Run creation without explicit project ownership', async () => {
    await expect(createRunStream({} as never, { project_id: '' } as never)).rejects.toMatchObject({
      message: 'A Run requires an active project',
      status: 422,
    });
  });

  it('freezes the explicit image binding and export preferences in the Run request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const inputs = buildRunInputs(defaultWorkflow, 'backend', { id: 'project-1', title: '雾港旧声' });

    await createRunStream(defaultWorkflow, inputs, undefined, 'run-1');

    const createOptions = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const body = JSON.parse(String(createOptions.body));
    expect(body.cover_asset_binding).toEqual({
      provider_profile_id: 'openai-compatible-image',
      model: 'gpt-image-2',
      candidate_count: 3,
      size: '1024x1536',
      quality: 'medium',
      timeout_seconds: 180,
      failure_policy: 'fail_run',
    });
    expect(body.export_preferences).toEqual({ format: 'zip', author: '', version_note: '' });
    expect(body.inputs).not.toHaveProperty('export_preferences');
  });

  it('submits an edited Artifact through the active graph decision', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const editedArtifact = {
      beats: [],
      climax: '高潮',
      resolution: '结局',
      character_outcomes: [],
    };

    await resolveRunDecision('run-1', 'decision-1', 'accept', 3, editedArtifact);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/runs/run-1/decisions/decision-1',
      expect.objectContaining({
        body: JSON.stringify({
          action: 'accept',
          domain_revision: 3,
          artifact: editedArtifact,
        }),
      }),
    );
  });

  it('sends a trimmed direction with a targeted regeneration decision', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await resolveRunDecision('run-1', 'chapter-decision-1', 'regenerate', 6, undefined, '  收紧追逐节奏  ');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/runs/run-1/decisions/chapter-decision-1',
      expect.objectContaining({
        body: JSON.stringify({
          action: 'regenerate',
          domain_revision: 6,
          direction: '收紧追逐节奏',
        }),
      }),
    );
  });

  it('resolves a chapter event reference through the immutable version API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ artifact: { content: '正文' } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getChapterVersion('run-1', 'chapter-1', 'chapter-1-v1');

    expect(result.artifact.content).toBe('正文');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/runs/run-1/chapters/chapter-1/versions/chapter-1-v1',
      { signal: undefined },
    );
  });
});
