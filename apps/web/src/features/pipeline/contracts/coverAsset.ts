export type CoverAssetRecord = {
  asset_id: string;
  run_id: string;
  operation_key: string;
  candidate_index: number;
  generation_attempt: number;
  sha256: string;
  mime_type: string;
  extension: string;
  width: number;
  height: number;
  size_bytes: number;
  provider_asset_id: string;
  revised_prompt: string;
  created_at: string;
  content_url: string;
};

export type CoverAssetCollection = {
  run_id: string;
  generation_attempt: number;
  items: CoverAssetRecord[];
};
