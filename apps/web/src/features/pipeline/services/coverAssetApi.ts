import type { CoverAssetCollection } from '../contracts';
import { RunApiError } from './runApi';

export async function getCoverAssets(runId: string, signal?: AbortSignal): Promise<CoverAssetCollection> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/cover-assets`, { signal });
  if (!response.ok) throw new RunApiError(`Unable to load cover assets for ${runId}`, response.status);
  return response.json();
}

export function coverAssetUrl(runId: string, assetId: string) {
  return `/api/runs/${encodeURIComponent(runId)}/cover-assets/${encodeURIComponent(assetId)}`;
}
