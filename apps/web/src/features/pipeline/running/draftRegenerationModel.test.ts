import { describe, expect, it } from 'vitest';
import {
  decisionQualityGuidance,
  regenerationSuggestionsForStage,
  resolveRegenerationDirection,
} from './draftRegenerationModel';

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

  it('projects hard and warning findings into one evidence-backed direction', () => {
    const guidance = decisionQualityGuidance({
      allowed_actions: ['regenerate', 'cancel'],
      regeneration_limit: 1,
      regeneration_used: 0,
      reason: {
        blocking_findings: [{
          claim: '24 小时后的事故在同一时段兑现',
          code: 'time_rule_conflict',
          evidence: '几分钟后撞击声响起',
        }],
        warning_findings: [{ claim: '解释略多', code: 'prose_density', evidence: '他解释了整个流程' }],
      },
    });

    expect(guidance.allowedActions).toEqual(['regenerate', 'cancel']);
    expect(guidance.blockingFindings[0].gate).toBe('blocking');
    expect(guidance.warningFindings[0].gate).toBe('warning');
    expect(guidance.recommendedDirection).toContain('几分钟后撞击声响起');
  });
});
