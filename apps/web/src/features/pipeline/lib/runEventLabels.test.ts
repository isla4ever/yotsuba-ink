import { describe, expect, it } from 'vitest';
import { runEventEntryLabel, runEventLabel } from './runEventLabels';

describe('runEventLabel (C1)', () => {
  it('maps known run events to writer language', () => {
    expect(runEventLabel('chapter_pipeline_step_completed')).toBe('章节工序完成');
    expect(runEventLabel('canon_facts_committed')).toBe('正典事实写回');
    expect(runEventLabel('memory_context_loaded')).toBe('事实层读取');
  });

  it('falls back to the generic 运行事件 instead of leaking raw type names', () => {
    expect(runEventLabel('some_internal_event')).toBe('运行事件');
    expect(runEventLabel('')).toBe('运行事件');
    expect(runEventLabel(undefined)).toBe('运行事件');
  });
});

describe('runEventEntryLabel (D9 provider retry visibility)', () => {
  it('maps provider events to writer language instead of internal names', () => {
    expect(runEventLabel('provider_attempt_started')).toBe('AI 服务调用中');
    expect(runEventLabel('provider_fallback_scheduled')).toBe('已切换备用服务');
    expect(runEventLabel('provider_fallback_blocked')).toBe('备用服务不可用');
  });

  it('surfaces the retry attempt count on retries and failures', () => {
    expect(runEventEntryLabel({ type: 'provider_attempt_started', attempt: 2 })).toBe('AI 服务重试中（第 2 次）');
    expect(runEventEntryLabel({ type: 'provider_attempt_started', attempt: 1 })).toBe('AI 服务调用中');
    expect(runEventEntryLabel({ type: 'provider_attempt_failed', attempt: 3 })).toBe('AI 服务调用失败（第 3 次）');
    expect(runEventEntryLabel({ type: 'chapter_completed' })).toBe('章节完成');
  });
});
