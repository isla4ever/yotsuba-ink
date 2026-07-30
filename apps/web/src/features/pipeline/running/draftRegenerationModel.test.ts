import { describe, expect, it } from 'vitest';
import { regenerationSuggestionsForStage, resolveRegenerationDirection } from './draftRegenerationModel';

describe('draft regeneration directions', () => {
  it('keeps three stage-specific suggestions', () => {
    expect(regenerationSuggestionsForStage({ type: 'summary' })).toHaveLength(3);
    expect(regenerationSuggestionsForStage({ type: 'outline' })[0]).toContain('卷内节拍');
    expect(regenerationSuggestionsForStage({ type: 'chapter_text' })[2]).toContain('段尾追读');
  });

  it('uses a trimmed custom direction before the selected suggestion', () => {
    expect(resolveRegenerationDirection('推荐方向', '  自定义方向  ')).toBe('自定义方向');
    expect(resolveRegenerationDirection('  推荐方向  ', '   ')).toBe('推荐方向');
  });
});
