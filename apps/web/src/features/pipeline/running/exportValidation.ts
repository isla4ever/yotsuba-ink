export type ExportValidationRow = {
  key: string;
  label: string;
  status: 'ready' | 'pending' | 'blocked';
  value: string;
};

const validationLabels: Record<string, string> = {
  chapters: '章节正文',
  cover: '封面资产',
  quality: '质量检查',
  canon: '事实冲突',
};

const validationValues: Record<string, string> = {
  ready: '已就绪',
  pending: '待完成',
  blocked: '未通过',
};

export const exportGateKeys = ['chapters', 'cover', 'quality', 'canon'] as const;

export function normalizeExportValidation(
  validation: Record<string, string>,
  facts: { hasChapters?: boolean; hasCoverAsset?: boolean } = {},
) {
  const normalized = Object.fromEntries(exportGateKeys.map((key) => [key, validation[key] || 'pending'])) as Record<string, string>;
  if (facts.hasChapters === false) normalized.chapters = 'pending';
  if (facts.hasCoverAsset === false) normalized.cover = 'pending';
  return normalized;
}

export function exportDeliveryReady(validation: Record<string, string>) {
  const normalized = normalizeExportValidation(validation);
  return exportGateKeys.every((key) => normalized[key] === 'ready');
}

export function exportValidationRows(validation: Record<string, string>): ExportValidationRow[] {
  const normalized = normalizeExportValidation(validation);
  return exportGateKeys.map((key) => {
    const rawValue = normalized[key];
    return {
      key,
      label: validationLabels[key],
      status: validationStatus(rawValue),
      value: validationValues[rawValue] ?? '状态待确认',
    };
  });
}

export function exportValidationValue(value: string) {
  return validationValues[value] ?? '状态待确认';
}

function validationStatus(value: string): ExportValidationRow['status'] {
  if (value === 'ready' || value === 'pending') return value;
  return 'blocked';
}
