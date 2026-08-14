import { describe, expect, it } from 'vitest';
import { regenerationSuggestionsForStage, resolveRegenerationDirection } from './draftRegenerationModel';

describe('draft regeneration directions', () => {
  it('keeps three stage-specific suggestions', () => {
    expect(regenerationSuggestionsForStage({ type: 'spine' })).toHaveLength(3);
    expect(regenerationSuggestionsForStage({ type: 'volumes' })[0]).toContain('本卷闭合');
    expect(regenerationSuggestionsForStage({ type: 'text' })[2]).toContain('段尾追读');
  });

  it('uses a trimmed custom direction before the selected suggestion', () => {
    expect(resolveRegenerationDirection('推荐方向', '  自定义方向  ')).toBe('自定义方向');
    expect(resolveRegenerationDirection('  推荐方向  ', '   ')).toBe('推荐方向');
  });
});
