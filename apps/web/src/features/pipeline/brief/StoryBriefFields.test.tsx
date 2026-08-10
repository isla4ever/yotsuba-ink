import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { WorkflowStage } from '../contracts';
import { buildBookScalePlan } from '../lib/bookScalePlan';
import { StoryBriefFields } from './StoryBriefFields';

function infoStage(): WorkflowStage {
  return {
    id: 'info',
    type: 'info',
    label: '创作立项定稿',
    provider_profile_id: 'openai-compatible',
    model_settings: { model: 'gpt-4.1-mini', temperature: 0.7, max_tokens: 1800, top_p: 0.95, timeout_seconds: 120 },
    prompt_template_id: 'prompt-info',
    input_schema: [
      { key: 'genre', label: '题材', type: 'select', required: true, default: '悬疑', options: ['悬疑', '都市'] },
      { key: 'book_scale_target_mode', label: '成书目标', type: 'select', required: true, default: 'total_chars', options: ['total_chars', 'total_chapters'] },
      { key: 'book_scale_target_value', label: '目标值', type: 'number', required: true, default: 100000 },
      { key: 'audience', label: '目标读者', type: 'text', required: true, default: '', placeholder: '例如：偏好强冲突、快节奏反转的悬疑读者' },
      { key: 'core_concept', label: '核心创意/冲突', type: 'textarea', required: true, default: '', hint: '立项只需要一个能撑起全书的核心冲突。', placeholder: '一句话说清冲突：谁+想要什么+被什么阻止' },
      { key: 'keywords', label: '关键词', type: 'tags', required: true, default: [], placeholder: '例如：孤岛、双时间线、身份互换' },
      { key: 'taboos', label: '禁忌/不要出现', type: 'textarea', required: true, default: '' },
    ],
  };
}

describe('StoryBriefFields book scale target', () => {
  it('renders hints under labels and placeholders inside empty controls', () => {
    const html = renderToStaticMarkup(<StoryBriefFields stage={infoStage()} onChange={() => undefined} />);

    expect(html).toContain('brief-field-hint');
    expect(html).toContain('立项只需要一个能撑起全书的核心冲突。');
    expect(html).toContain('一句话说清冲突：谁+想要什么+被什么阻止');
    expect(html).toContain('例如：偏好强冲突、快节奏反转的悬疑读者');
    // Tags fall back to the interaction cue only when no placeholder is provided.
    expect(html).toContain('例如：孤岛、双时间线、身份互换');
  });

  it('shows one mutually exclusive target control with a derived scale preview', () => {
    const html = renderToStaticMarkup(<StoryBriefFields stage={infoStage()} onChange={() => undefined} />);

    expect(html).toContain('总字数');
    expect(html).toContain('总章数');
    expect(html).toContain('10 万字');
    expect(html).toContain('4 卷 / 50 章');
    expect(html).toContain('1,600-2,400 字');
  });

  it('derives the same book shape from equivalent word and chapter goals', () => {
    const byWords = buildBookScalePlan('total_chars', 100000);
    const byChapters = buildBookScalePlan('total_chapters', 50);
    expect(byWords.total_chapters).toBe(50);
    expect(byWords.chapters_per_volume).toEqual([13, 13, 12, 12]);
    expect(byChapters.total_chars).toBe(100000);
    expect(byChapters.chapters_per_volume).toEqual(byWords.chapters_per_volume);
  });
});
