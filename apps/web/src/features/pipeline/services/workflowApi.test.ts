import { afterEach, describe, expect, it, vi } from 'vitest';
import { getDefaultWorkflowDefinition } from './workflowApi';
import { defaultWorkflowId } from '../lib/officialWorkflows';

describe('workflow API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('hydrates the planning workflow from the server authority', async () => {
    const payload = { id: defaultWorkflowId, provider_profiles: [{ id: 'live-provider' }] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getDefaultWorkflowDefinition();

    expect(result).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith('/api/workflows/default');
  });
});
