import { describe, expect, it } from 'vitest';
import { draftsEqual, shouldConfirmUnsavedDraft, shouldPromptBlockedNavigation } from './useUnsavedDraftGuard';

describe('unsaved draft guard', () => {
  it('guards writable dirty drafts but leaves clean and read-only views alone', () => {
    expect(shouldConfirmUnsavedDraft(true)).toBe(true);
    expect(shouldConfirmUnsavedDraft(false)).toBe(false);
    expect(shouldConfirmUnsavedDraft(true, true)).toBe(false);
  });

  it('detects nested writeback changes without treating an equal clone as dirty', () => {
    const source = {
      chapter: '第一章',
      fact_reveals: [{ anchor: '旧港', fact: '母带存在', impact: '调查继续' }],
      foreshadow: [{ name: '失真录音', status: '投放' }],
    };
    expect(draftsEqual(source, structuredClone(source))).toBe(true);

    const edited = structuredClone(source);
    edited.fact_reveals[0].impact = '调查转向实验室';
    expect(draftsEqual(source, edited)).toBe(false);
  });

  it('does not reopen a dismissed route-leave prompt before the blocker resets', () => {
    expect(shouldPromptBlockedNavigation('blocked', false, false)).toBe(true);
    expect(shouldPromptBlockedNavigation('blocked', false, true)).toBe(false);
    expect(shouldPromptBlockedNavigation('blocked', true, false)).toBe(false);
    expect(shouldPromptBlockedNavigation('unblocked', false, false)).toBe(false);
  });
});
