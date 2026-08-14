import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createRunStream,
  getContextManifest,
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

  it('submits only the project workflow authority and user Run inputs', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const inputs = buildRunInputs(defaultWorkflow, 'backend', { id: 'project-1', title: '雾港旧声' });

    await createRunStream(defaultWorkflow, inputs, undefined, 'run-1');

    const createOptions = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const body = JSON.parse(String(createOptions.body));
    expect(body.workflow_id).toBe('default-novel-workflow');
    expect(body).not.toHaveProperty('provider_bindings');
    expect(body).not.toHaveProperty('cover_asset_binding');
    expect(body).not.toHaveProperty('workflow_revision');
    expect(body).not.toHaveProperty('quality_mode');
    expect(body).not.toHaveProperty('scale_profile');
    expect(body.export_preferences).toEqual({ format: 'zip', author: '', version_note: '' });
    expect(body.inputs).not.toHaveProperty('export_preferences');
    expect(body.inputs.length_envelope).toEqual({ word_target_soft: 100000, chapter_target_soft: null });
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

  it('loads a frozen Context Manifest by its read-model reference', async () => {
    const record = {
      run_id: 'run-1',
      manifest_id: `manifest-${'a'.repeat(64)}`,
      chapter_id: 'chapter-1',
      attempt: 1,
      manifest: {
        task: 'chapter-1',
        required: ['detail.chapter'],
        optional: [],
        forbidden: ['full_canon'],
        snippets: [],
        budget: { input_chars: 10, output_tokens: 100 },
        manifest_hash: 'b'.repeat(64),
      },
      created_at: '2026-08-12T00:00:00Z',
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(record), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getContextManifest('run-1', record.manifest_id)).resolves.toEqual(record);
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/runs/run-1/context-manifests/${record.manifest_id}`,
      { signal: undefined },
    );
  });
});
