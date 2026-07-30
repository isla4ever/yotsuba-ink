import { describe, expect, it } from 'vitest';
import { exportValidationRows, exportValidationValue } from './exportValidation';

describe('export validation presentation', () => {
  it('maps known validation fields to writer-facing labels', () => {
    expect(exportValidationRows({ chapters: 'ready', cover: 'pending', quality: 'blocked', canon: 'ready' })).toEqual([
      { key: 'chapters', label: '章节正文', status: 'ready', value: '已就绪' },
      { key: 'cover', label: '封面资产', status: 'pending', value: '待完成' },
      { key: 'quality', label: '质量检查', status: 'blocked', value: '未通过' },
      { key: 'canon', label: '事实冲突', status: 'ready', value: '已就绪' },
    ]);
  });

  it('does not expose unknown backend keys and still renders the four delivery gates', () => {
    expect(exportValidationRows({ internal_schema_gate: 'server_retry', delivery_lock: 'ready' })).toEqual([
      { key: 'chapters', label: '章节正文', status: 'pending', value: '待完成' },
      { key: 'cover', label: '封面资产', status: 'pending', value: '待完成' },
      { key: 'quality', label: '质量检查', status: 'pending', value: '待完成' },
      { key: 'canon', label: '事实冲突', status: 'pending', value: '待完成' },
    ]);
    expect(exportValidationValue('internal_ready_state')).toBe('状态待确认');
  });

  it('shows all four gates as pending when validation has not returned', () => {
    expect(exportValidationRows({})).toHaveLength(4);
    expect(exportValidationRows({}).every((row) => row.status === 'pending')).toBe(true);
  });
});
