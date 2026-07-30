import { describe, expect, it } from 'vitest';
import { candidatePreviewText } from './stageCandidatePreview';

describe('stage candidate preview', () => {
  it('uses readable stage fields instead of serializing an artifact', () => {
    expect(candidatePreviewText({ title: '雾港', full_synopsis: '一场失忆案撕开港城旧约。' }))
      .toBe('雾港\n一场失忆案撕开港城旧约。');
    expect(candidatePreviewText({ artifact: { volumes: [{ title: '第一卷', volume_goal: '找回证据' }] } }))
      .toBe('第一卷');
  });

  it('rejects legacy JSON preview strings and exposes no internal keys', () => {
    const preview = candidatePreviewText({ schema_version: '1', commit_signature: 'secret' }, '{"schema_version":"1"}');

    expect(preview).toBe('候选产物已生成，当前结构暂不支持内容预览。');
    expect(preview).not.toContain('schema_version');
    expect(preview).not.toContain('{');
  });
});
