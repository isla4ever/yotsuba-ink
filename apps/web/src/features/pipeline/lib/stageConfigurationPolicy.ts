import type { QualityMode, WorkflowStage } from '../contracts';

export type TemperaturePreset = 'stable' | 'balanced' | 'active' | 'custom';

export const temperaturePresets = [
  { id: 'stable', label: '稳定', value: 0.4 },
  { id: 'balanced', label: '平衡', value: 0.7 },
  { id: 'active', label: '活跃', value: 1 },
] as const;

const textStageTypes = new Set<WorkflowStage['type']>(['summary', 'outline', 'detail_outline', 'chapter_text']);
const hiddenCoverFields = new Set(['aspect_ratio', 'asset_retry_limit', 'image_budget_usd']);
const versionCompareFields = new Set([
  'enable_version_compare',
  'version_candidate_count',
  'judge_provider_profile_id',
  'judge_model',
  'compare_dimensions',
]);

export function temperaturePresetFor(value: number): TemperaturePreset {
  return temperaturePresets.find((preset) => Math.abs(preset.value - value) < 0.001)?.id ?? 'custom';
}

export function clampTemperature(value: number) {
  if (!Number.isFinite(value)) return 0.7;
  return Math.min(1.4, Math.max(0, value));
}

export function hiddenStageField(stage: WorkflowStage, fieldKey: string) {
  if (stage.type === 'chapter_text' && versionCompareFields.has(fieldKey)) return true;
  return stage.type === 'cover_image' && (hiddenCoverFields.has(fieldKey) || fieldKey === 'image_quality');
}

export function coverImageQuality(stage: WorkflowStage) {
  return stage.input_schema.find((field) => field.key === 'image_quality');
}

export function coverAspectRatio(stage: WorkflowStage) {
  return String(stage.input_schema.find((field) => field.key === 'aspect_ratio')?.default ?? '2:3');
}

export function derivedQualitySummary(stage: WorkflowStage, mode: QualityMode) {
  const minScore = mode === 'deep' && textStageTypes.has(stage.type)
    ? Math.max(stage.quality_policy.min_score, 0.84)
    : stage.quality_policy.min_score;
  if (mode === 'fast') return `阈值 ${minScore.toFixed(2)} · 记录问题，不自动重试`;
  if (mode === 'deep') return `阈值 ${minScore.toFixed(2)} · 生成后等待人工定稿`;
  return `阈值 ${minScore.toFixed(2)} · 未通过时按阶段规则修订`;
}

export function memoryPolicySummary(stage: WorkflowStage) {
  if (!stage.memory_policy.read && !stage.memory_policy.write) return '本阶段不读取或更新创作设定';
  if (stage.memory_policy.read && stage.memory_policy.write) return '读取已确认设定，定稿后更新对应事实';
  return stage.memory_policy.read ? '仅读取已确认设定' : '定稿后更新对应事实';
}
