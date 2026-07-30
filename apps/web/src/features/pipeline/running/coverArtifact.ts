import { list, numberValue, objectList, objectRecord, parseArtifactRecord, text } from './artifactParsing';

export type CoverArtifact = {
  brief: string;
  visual_keywords: string[];
  composition: string;
  prompt: string;
  copy_suggestions: string[];
  candidates: Array<{
    id: string;
    image_url: string;
    composition: string;
    palette: string;
    quality_summary: string;
    asset_status: 'planned' | 'generating' | 'ready' | 'failed' | 'blocked';
    asset_source: 'production' | 'fixture' | 'legacy';
    generation_key: string;
    asset_id: string;
    mime_type: string;
    width: number;
    height: number;
    size_bytes: number;
    sha256: string;
    provider_profile_id: string;
    model: string;
    attempt: number;
    error_code: string;
    error_message: string;
  }>;
  selected_candidate_id: string;
  asset_generation: {
    status: 'planned' | 'generating' | 'partial' | 'ready' | 'failed';
    total: number;
    ready_count: number;
    failed_count: number;
    provider_profile_id: string;
    model: string;
    size: string;
    quality: string;
    updated_at: string;
  };
};

export function coverArtifact(value: string): CoverArtifact {
  const record = parseArtifactRecord(value);
  return {
    brief: text(record?.brief, ''),
    visual_keywords: list(record?.visual_keywords, []),
    composition: text(record?.composition, ''),
    prompt: text(record?.prompt, ''),
    copy_suggestions: list(record?.copy_suggestions, []),
    candidates: objectList<Record<string, unknown>>(record?.candidates, []).map((candidate) => ({
      id: text(candidate.id, ''),
      image_url: text(candidate.image_url, ''),
      composition: text(candidate.composition, ''),
      palette: text(candidate.palette, ''),
      quality_summary: text(candidate.quality_summary, ''),
      asset_status: coverAssetStatus(candidate.asset_status, candidate.image_url),
      asset_source: coverAssetSource(candidate.asset_source),
      generation_key: text(candidate.generation_key, ''),
      asset_id: text(candidate.asset_id, ''),
      mime_type: text(candidate.mime_type, ''),
      width: numberValue(candidate.width, 0),
      height: numberValue(candidate.height, 0),
      size_bytes: numberValue(candidate.size_bytes, 0),
      sha256: text(candidate.sha256, ''),
      provider_profile_id: text(candidate.provider_profile_id, ''),
      model: text(candidate.model, ''),
      attempt: numberValue(candidate.attempt, 0),
      error_code: text(candidate.error_code, ''),
      error_message: text(candidate.error_message, ''),
    })),
    selected_candidate_id: text(record?.selected_candidate_id, ''),
    asset_generation: normalizeCoverGeneration(record?.asset_generation),
  };
}

function normalizeCoverGeneration(value: unknown): CoverArtifact['asset_generation'] {
  const record = objectRecord(value);
  const status = String(record?.status ?? 'planned');
  return {
    status: ['planned', 'generating', 'partial', 'ready', 'failed'].includes(status) ? status as CoverArtifact['asset_generation']['status'] : 'planned',
    total: numberValue(record?.total, 0),
    ready_count: numberValue(record?.ready_count, 0),
    failed_count: numberValue(record?.failed_count, 0),
    provider_profile_id: text(record?.provider_profile_id, ''),
    model: text(record?.model, ''),
    size: text(record?.size, ''),
    quality: text(record?.quality, ''),
    updated_at: text(record?.updated_at, ''),
  };
}

function coverAssetStatus(value: unknown, imageUrl: unknown): CoverArtifact['candidates'][number]['asset_status'] {
  const status = String(value ?? '');
  if (['planned', 'generating', 'ready', 'failed', 'blocked'].includes(status)) return status as CoverArtifact['candidates'][number]['asset_status'];
  return text(imageUrl, '') ? 'ready' : 'planned';
}

function coverAssetSource(value: unknown): CoverArtifact['candidates'][number]['asset_source'] {
  const source = String(value ?? '');
  return ['production', 'fixture', 'legacy'].includes(source) ? source as CoverArtifact['candidates'][number]['asset_source'] : 'legacy';
}
