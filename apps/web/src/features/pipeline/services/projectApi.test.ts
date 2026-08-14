import { afterEach, describe, expect, it, vi } from 'vitest';
import { getProjectSummary, listProjects, ProjectApiError } from './projectApi';

describe('Project API current contract', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('rejects incomplete records instead of injecting compatibility defaults', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([
      { id: 'project-1', workflow_id: 'workflow-1' },
    ]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })));

    const error = await listProjects().catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(ProjectApiError);
    expect(error).toMatchObject({ status: 502 });
  });

  it('strictly validates the shared latest Run history projection', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      project: {
        accent_hue: 24,
        created_at: '2026-08-11T00:00:00Z',
        id: 'project-1',
        latest_run_id: 'run-1',
        status: 'active',
        summary: '',
        title: '星图之书',
        updated_at: '2026-08-11T00:00:00Z',
        workflow_id: 'workflow-1',
      },
      latest_run: { run_id: 'run-1' },
      title: '星图之书',
      status: 'running',
      current_stage: { id: 'cast', label: '人物编排', type: 'cast' },
      completed_stage_ids: ['brief', 'spine'],
      words: 0,
      updated_at: '2026-08-11T00:00:00Z',
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })));

    const error = await getProjectSummary('project-1').catch((reason: unknown) => reason);

    expect(error).toMatchObject({ name: 'RunApiError', status: 502 });
  });
});
