import type { QualityMode, WorkflowStage } from '../contracts';

export type TemperaturePreset = 'stable' | 'balanced' | 'active' | 'custom';

export const temperaturePresets = [
  { id: 'stable', label: '稳定', value: 0.4 },
  { id: 'balanced', label: '平衡', value: 0.7 },
  { id: 'active', label: '活跃', value: 1 },
] as const;

const hiddenCoverFields = new Set(['image_size']);

export function temperaturePresetFor(value: number): TemperaturePreset {
  return temperaturePresets.find((preset) => Math.abs(preset.value - value) < 0.001)?.id ?? 'custom';
}

export function clampTemperature(value: number) {
  if (!Number.isFinite(value)) return 0.7;
  return Math.min(1.4, Math.max(0, value));
}

export function hiddenStageField(stage: WorkflowStage, fieldKey: string) {
  return stage.type === 'cover' && (hiddenCoverFields.has(fieldKey) || fieldKey === 'image_quality');
}

export function coverImageQuality(stage: WorkflowStage) {
  return stage.input_schema.find((field) => field.key === 'image_quality');
}

export function coverImageSize(stage: WorkflowStage) {
  return String(stage.input_schema.find((field) => field.key === 'image_size')?.default ?? '');
}

export function derivedQualitySummary(stage: WorkflowStage, mode: QualityMode) {
  void stage;
  if (mode === 'fast') return '固定三路审稿 · 策略自动接受';
  if (mode === 'deep') return '固定三路审稿 · 全部必需 · 人工决策';
  return '固定三路审稿 · 文风可选 · 人工决策';
}

export function memoryPolicySummary(stage: WorkflowStage) {
  if (stage.type === 'text') return '正文只读冻结规划；Evidence 经确认后写入事实账本';
  if (stage.type === 'cover' || stage.type === 'export') return '不读写 Canon、Wiki 或人物注册表';
  return '只读已提交上游 Artifact；定稿仅写当前阶段 Artifact';
}
