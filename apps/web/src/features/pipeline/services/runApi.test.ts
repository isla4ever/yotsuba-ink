import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createRunStream,
  getContextManifest,
  getChapterVersion,
  getRun,
  getRunPresentationSnapshot,
  getStageArtifactDraft,
  isRunNotFoundError,
  resolveRunDecision,
  RunApiError,
  saveStageArtifactDraft,
} from './runApi';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { buildRunInputs } from '../state/runInputs';
import { defaultWorkflowId } from '../lib/officialWorkflows';

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

  it('treats a run retired by the current contract as unrecoverable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: 'run_contract_retired',
        message: '该运行不符合当前生产合同，已从主线历史中隔离。',
      },
    }), {
      status: 409,
      headers: { 'Content-Type': 'application/json' },
    })));

    const error = await getRun('retired-run').catch((reason: unknown) => reason);

    expect(error).toMatchObject({
      name: 'RunApiError',
      status: 409,
      code: 'run_contract_retired',
    });
    expect(isRunNotFoundError(error)).toBe(true);
  });

  it('loads every committed artifact referenced by the run read model', async () => {
    const envelope = {
      definition: { run_id: 'run-branch' },
      read_model: {
        run_id: 'run-branch',
        artifact_refs: {
          brief: 'brief-committed-1',
          spine: 'spine-committed-1',
        },
      },
    };
    const records = {
      'brief-committed-1': artifactRecord('run-branch', 'brief', 'brief-committed-1'),
      'spine-committed-1': artifactRecord('run-branch', 'spine', 'spine-committed-1'),
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/runs/run-branch') return jsonResponse(envelope);
      const parts = url.split('/');
      const artifactId = parts[parts.length - 1] ?? '';
      return jsonResponse(records[artifactId as keyof typeof records]);
    });
    vi.stubGlobal('fetch', fetchMock);

    const snapshot = await getRunPresentationSnapshot('run-branch');

    expect(snapshot.envelope).toEqual(envelope);
    expect(snapshot.committedArtifacts.map((item) => item.artifact_id)).toEqual([
      'brief-committed-1',
      'spine-committed-1',
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('loads accepted chapter versions for terminal presentation without opening the event stream', async () => {
    const envelope = {
      definition: { run_id: 'run-terminal' },
      read_model: { run_id: 'run-terminal', status: 'completed', artifact_refs: {} },
    };
    const chapter = {
      run_id: 'run-terminal',
      chapter_id: 'chapter-1',
      version_id: 'chapter-1-v2',
      artifact: {
        chapter_id: 'chapter-1',
        version_id: 'chapter-1-v2',
        title: '第一章',
        content: '正文',
        author_status: 'accepted',
      },
      signature: 'b'.repeat(64),
      created_at: '2026-08-14T00:00:00Z',
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === '/api/runs/run-terminal') return jsonResponse(envelope);
      if (String(input) === '/api/runs/run-terminal/chapters') return jsonResponse({ run_id: 'run-terminal', chapters: [chapter] });
      throw new Error(`unexpected request: ${String(input)}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const snapshot = await getRunPresentationSnapshot('run-terminal');

    expect(snapshot.acceptedChapters).toEqual([chapter]);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      '/api/runs/run-terminal',
      '/api/runs/run-terminal/chapters',
    ]);
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
    const inputs = buildRunInputs(defaultWorkflow, 'backend', { id: 'project-1' });

    await createRunStream(defaultWorkflow, inputs, undefined, 'run-1');

    const createOptions = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const body = JSON.parse(String(createOptions.body));
    expect(body.workflow_id).toBe(defaultWorkflowId);
    expect(body).not.toHaveProperty('provider_bindings');
    expect(body).not.toHaveProperty('cover_asset_binding');
    expect(body).not.toHaveProperty('workflow_revision');
    expect(body).not.toHaveProperty('quality_mode');
    expect(body).not.toHaveProperty('scale_profile');
    expect(body.export_preferences).toEqual({ format: 'zip', author: '', version_note: '' });
    expect(body.inputs).not.toHaveProperty('export_preferences');
    expect(body.inputs.length_envelope).toEqual({ word_target_soft: 100000 });
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

  it('loads and saves a draft without using the decision endpoint', async () => {
    const record = {
      draft_id: 'volumes-draft-1',
      run_id: 'run-1',
      stage_id: 'volumes',
      decision_id: 'run-1:volumes:candidate-1',
      domain_revision: 3,
      source_artifact_id: 'volumes-candidate-1',
      payload: { volumes: [] },
      signature: 'a'.repeat(64),
      created_at: '2026-08-15T00:00:00Z',
    };
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(record));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getStageArtifactDraft('run-1', record.decision_id)).resolves.toEqual(record);
    await expect(saveStageArtifactDraft(
      'run-1',
      record.decision_id,
      3,
      record.source_artifact_id,
      record.payload,
    )).resolves.toEqual(record);

    const encoded = encodeURIComponent(record.decision_id);
    expect(fetchMock.mock.calls[0]).toEqual([
      `/api/runs/run-1/stage-drafts/${encoded}`,
      { signal: undefined },
    ]);
    expect(fetchMock.mock.calls[1]).toEqual([
      `/api/runs/run-1/stage-drafts/${encoded}`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          domain_revision: 3,
          source_artifact_id: record.source_artifact_id,
          artifact: record.payload,
        }),
      }),
    ]);
  });

  it('treats a missing current draft as an empty restore', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(null)));

    await expect(getStageArtifactDraft('run-1', 'decision-1')).resolves.toBeNull();
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

function artifactRecord(runId: string, stageId: 'brief' | 'spine', artifactId: string) {
  return {
    artifact_id: artifactId,
    run_id: runId,
    stage_id: stageId,
    status: 'committed',
    payload: stageId === 'brief' ? { title: '潮汐证词' } : { turns: [] },
    signature: 'a'.repeat(64),
    created_at: '2026-08-14T00:00:00Z',
    source: 'decision:test',
  };
}

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
