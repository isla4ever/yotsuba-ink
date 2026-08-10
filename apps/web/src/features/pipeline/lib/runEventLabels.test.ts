import { describe, expect, it } from 'vitest';
import { runEventEntryLabel, runEventLabel } from './runEventLabels';

describe('runEventLabel (Phase 26 Graph events)', () => {
  it('maps known run events to writer language', () => {
    expect(runEventLabel('node.completed')).toBe('节点完成');
    expect(runEventLabel('artifact.committed')).toBe('产物已正式写回');
    expect(runEventLabel('decision.required')).toBe('等待人工决定');
    expect(runEventLabel('writeback.committed')).toBe('写回事务已提交');
  });

  it('falls back to the generic 运行事件 instead of leaking raw type names', () => {
    expect(runEventLabel('some_internal_event')).toBe('运行事件');
    expect(runEventLabel('')).toBe('运行事件');
    expect(runEventLabel(undefined)).toBe('运行事件');
  });
});

describe('runEventEntryLabel', () => {
  it('uses the same stable Graph labels without retry metadata', () => {
    expect(runEventEntryLabel({ type: 'provider.delta' })).toBe('内容生成中');
    expect(runEventEntryLabel({ type: 'node.failed' })).toBe('节点失败');
  });
});
