import type { CoverArtifact } from './stageArtifacts';

export type CoverAssetPresentation = {
  composition: string;
  imageUrl: string;
  palette: string;
  qualitySummary: string;
  title: string;
};

export type CoverDeliveryCheck = {
  detail: string;
  key: string;
  label: string;
  ready: boolean;
};

export type CoverReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export function coverAssetFromArtifact(value: unknown): CoverAssetPresentation {
  const record = objectRecord(value);
  const candidates = Array.isArray(record?.candidates) ? record.candidates.map(objectRecord).filter(Boolean) : [];
  const selectedId = stringValue(record?.selected_candidate_id);
  const selected = candidates.find((candidate) => stringValue(candidate?.id) === selectedId) ?? candidates[0];
  return {
    composition: stringValue(selected?.composition, record?.composition),
    imageUrl: coverImageSource(selected?.image_url),
    palette: stringValue(selected?.palette),
    qualitySummary: stringValue(selected?.quality_summary),
    title: stringValue(selected?.id, record?.title, record?.brief),
  };
}

export function coverDeliveryChecks(artifact: CoverArtifact): CoverDeliveryCheck[] {
  const selected = artifact.candidates.find((candidate) => candidate.id === artifact.selected_candidate_id);
  const selectedAsset = selected?.asset_status === 'ready' ? coverImageSource(selected.image_url) : '';
  return [
    { key: 'brief', label: '封面简报', ready: Boolean(artifact.brief.trim()), detail: artifact.brief ? '创作目标已明确' : '缺少封面创作目标' },
    { key: 'composition', label: '画面构图', ready: Boolean((selected?.composition || artifact.composition).trim()), detail: selected?.composition || artifact.composition || '缺少构图说明' },
    { key: 'prompt', label: '图片提示词', ready: Boolean(artifact.prompt.trim()), detail: artifact.prompt ? '提示词已准备' : '缺少图片生成提示词' },
    { key: 'selection', label: '方案选择', ready: Boolean(selected), detail: selected ? `已选择 ${selected.id}` : '尚未选择候选方案' },
    { key: 'asset', label: '图片资产', ready: Boolean(selectedAsset), detail: selectedAsset ? `${selected?.width || 0}x${selected?.height || 0} 已保存` : '正式候选尚未生成成功的图片' },
  ];
}

export function coverReadiness(artifact: CoverArtifact): CoverReadiness {
  const checks = coverDeliveryChecks(artifact);
  const completed = checks.filter((check) => check.ready).length;
  return {
    completed,
    missingLabels: checks.filter((check) => !check.ready).map((check) => check.label),
    ready: completed === checks.length,
    total: checks.length,
  };
}

export function formalCoverCandidateId(artifact: CoverArtifact) {
  const selected = artifact.candidates.find((candidate) => candidate.id === artifact.selected_candidate_id);
  return selected?.asset_status === 'ready' && coverImageSource(selected.image_url) ? selected.id : '';
}

export function coverImageSource(value: unknown) {
  const source = stringValue(value);
  if (!source) return '';
  if (source.startsWith('/') || /^https?:\/\//i.test(source)) return source;
  return /^data:image\/(?:png|jpe?g|webp);base64,/i.test(source) ? source : '';
}

export function coverCandidateLabel(index: number) {
  return `方案 ${String(index + 1).padStart(2, '0')}`;
}

export function coverCandidateStatusLabel(status: CoverArtifact['candidates'][number]['asset_status']) {
  return {
    planned: '等待生成',
    generating: '正在生成',
    ready: '资产就绪',
    failed: '生成失败',
    blocked: '需人工处理',
  }[status];
}

export function coverQualityPercent(score: unknown): number | null {
  if (score === '' || score == null) return null;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return null;
  const percent = numeric >= 0 && numeric <= 1 ? numeric * 100 : numeric;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

export function coverStageSummary(artifact: CoverArtifact, score: unknown) {
  const checks = coverDeliveryChecks(artifact);
  const readyCount = checks.filter((check) => check.ready).length;
  const imageReady = checks.find((check) => check.key === 'asset')?.ready ?? false;
  const qualityPercent = coverQualityPercent(score);
  return {
    description: imageReady
      ? '封面方案与真实图片资产已进入交付准备。'
      : '封面方案已生成，图片资产尚未返回。',
    metrics: [
      `${artifact.candidates.length} 个方案`,
      `准备 ${readyCount}/${checks.length}`,
      imageReady ? '图片已返回' : '图片待生成',
      ...(qualityPercent == null ? [] : [`质量 ${qualityPercent}%`]),
    ],
  };
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function stringValue(...values: unknown[]) {
  return values.map((value) => String(value ?? '').trim()).find(Boolean) ?? '';
}
