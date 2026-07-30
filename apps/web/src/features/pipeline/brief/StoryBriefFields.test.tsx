import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { WorkflowStage } from '../contracts';
import { applyTargetWordsRange } from '../lib/stageConfig';
import { StoryBriefFields } from './StoryBriefFields';

function infoStage(): WorkflowStage {
  return {
    id: 'info',
    type: 'info_recommend',
    label: '创作立项定稿',
    params: {},
    input_refs: [],
    output_key: 'info_recommend',
    memory_policy: { read: false, write: true, scope: 'project', kinds: [] },
    provider_profile_id: 'openai-compatible',
    model_settings: { model: 'gpt-4.1-mini', temperature: 0.7, max_tokens: 1800, top_p: 0.95, timeout_seconds: 120 },
    prompt_template_id: 'prompt-info',
    input_schema: [
      { key: 'genre', label: '题材', type: 'select', required: true, default: '悬疑', options: ['悬疑', '都市'] },
      { key: 'target_length', label: '目标篇幅', type: 'select', required: true, default: '长篇', options: ['短篇', '中篇', '长篇', '系列长篇'] },
      { key: 'target_words_range', label: '目标字数区间', type: 'select', required: true, default: '80-120 万字', options: ['1-3 万字', '5-10 万字', '20-40 万字', '80-120 万字', '120 万字以上'], hint: '篇幅只选这一次，目标规模会随字数区间自动确定。' },
      { key: 'audience', label: '目标读者', type: 'text', required: true, default: '', placeholder: '例如：偏好强冲突、快节奏反转的悬疑读者' },
      { key: 'core_concept', label: '核心创意/冲突', type: 'textarea', required: true, default: '', hint: '立项只需要一个能撑起全书的核心冲突。', placeholder: '一句话说清冲突：谁+想要什么+被什么阻止' },
      { key: 'keywords', label: '关键词', type: 'tags', required: true, default: [], placeholder: '例如：孤岛、双时间线、身份互换' },
      { key: 'taboos', label: '禁忌/不要出现', type: 'textarea', required: true, default: '' },
    ],
    output_schema: {},
    quality_policy: { min_score: 0.8, retry_on_fail: true, require_human_review: false, checks: [] },
    variant_policy: { enabled: false, candidate_count: 1, judge_provider_profile_id: 'inherit', judge_model: 'gpt-4.1-mini', dimensions: [], retry_on_fail: false },
  };
}

describe('StoryBriefFields (Phase 12 A3/B2)', () => {
  it('renders hints under labels and placeholders inside empty controls', () => {
    const html = renderToStaticMarkup(<StoryBriefFields stage={infoStage()} onChange={() => undefined} />);

    expect(html).toContain('brief-field-hint');
    expect(html).toContain('立项只需要一个能撑起全书的核心冲突。');
    expect(html).toContain('一句话说清冲突：谁+想要什么+被什么阻止');
    expect(html).toContain('例如：偏好强冲突、快节奏反转的悬疑读者');
    // Tags fall back to the interaction cue only when no placeholder is provided.
    expect(html).toContain('例如：孤岛、双时间线、身份互换');
  });

  it('shows a single length control: the word-count range renders, the coarse tier does not', () => {
    const html = renderToStaticMarkup(<StoryBriefFields stage={infoStage()} onChange={() => undefined} />);

    expect(html).toContain('目标字数区间');
    expect(html).toContain('篇幅只选这一次');
    expect(html).not.toContain('id="brief-target_length"');
  });

  it('derives target_length from the chosen words range so both prompt inputs stay consistent', () => {
    const fieldDefault = (stage: WorkflowStage, key: string) => stage.input_schema.find((field) => field.key === key)?.default;

    const shortForm = applyTargetWordsRange(infoStage(), '1-3 万字');
    expect(fieldDefault(shortForm, 'target_words_range')).toBe('1-3 万字');
    expect(fieldDefault(shortForm, 'target_length')).toBe('短篇');

    expect(fieldDefault(applyTargetWordsRange(infoStage(), '5-10 万字'), 'target_length')).toBe('中篇');
    expect(fieldDefault(applyTargetWordsRange(infoStage(), '20-40 万字'), 'target_length')).toBe('长篇');
    expect(fieldDefault(applyTargetWordsRange(infoStage(), '80-120 万字'), 'target_length')).toBe('长篇');
    expect(fieldDefault(applyTargetWordsRange(infoStage(), '120 万字以上'), 'target_length')).toBe('系列长篇');

    // Unknown ranges update the range but never corrupt the existing tier.
    const custom = applyTargetWordsRange(infoStage(), '自定义区间');
    expect(fieldDefault(custom, 'target_words_range')).toBe('自定义区间');
    expect(fieldDefault(custom, 'target_length')).toBe('长篇');
  });
});
