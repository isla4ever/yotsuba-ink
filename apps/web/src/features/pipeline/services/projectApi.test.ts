import { afterEach, describe, expect, it, vi } from 'vitest';
import { listProjects, ProjectApiError } from './projectApi';

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
});
