import type { InputField, WorkflowStage } from '../contracts';

export type StageConfigurationReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

const artifactLabels: Record<WorkflowStage['type'], string> = {
  info_recommend: '立项设定与人物关系',
  summary: '完整梗概与故事结构',
  outline: '分卷节拍与冲突推进',
  detail_outline: '章节施工图与伏笔矩阵',
  chapter_text: '章节正文与修订版本',
  cover_image: '封面方案与视觉提示词',
  export_artifact: '校验清单与交付文件包',
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
