import { afterEach, describe, expect, it, vi } from 'vitest';
import { coverAssetUrl, getCoverAssets } from './coverAssetApi';

describe('cover asset API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('loads the active immutable candidate collection', async () => {
    const payload = { run_id: 'run 1', generation_attempt: 2, items: [] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getCoverAssets('run 1')).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith('/api/runs/run%201/cover-assets', { signal: undefined });
  });

  it('builds an encoded immutable content URL', () => {
    expect(coverAssetUrl('run 1', 'cover/a')).toBe('/api/runs/run%201/cover-assets/cover%2Fa');
  });
});
