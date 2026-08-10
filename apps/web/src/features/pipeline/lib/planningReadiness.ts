import type { InputField, WorkflowStage } from '../contracts';

export type StageConfigurationReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

const artifactLabels: Record<WorkflowStage['type'], string> = {
  info: '创作契约与世界规则',
  characters: '人物职责、关系与出场窗口',
  summary: '故事脊柱与人物结局',
  outline: '分卷节拍与叙事窗口',
  detail: '章节施工图、义务与交接',
  text: '章节正文定稿',
  cover: '封面简报与选定资产',
  export: '版本选择与交付格式',
};

export function stageArtifactLabel(stage: WorkflowStage) {
  return artifactLabels[stage.type];
}

export function stageConfigurationReadiness(stage: WorkflowStage): StageConfigurationReadiness {
  const required = stage.input_schema.filter((field) => field.required);
  const missing = required.filter((field) => !hasConfiguredValue(field));
  return {
    completed: required.length - missing.length,
    missingLabels: missing.map((field) => field.label),
    ready: missing.length === 0,
    total: required.length,
  };
}

function hasConfiguredValue(field: InputField) {
  const value = field.default;
  if (field.type === 'boolean') return typeof value === 'boolean';
  if (field.type === 'number') return typeof value === 'number' && Number.isFinite(value);
  if (Array.isArray(value)) return value.some((item) => String(item).trim());
  return String(value ?? '').trim().length > 0;
}
