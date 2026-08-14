import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { WorkflowStage } from '../contracts';
import { StoryBriefFields } from './StoryBriefFields';

function briefStage(): WorkflowStage {
  return {
    id: 'brief',
    type: 'brief',
    label: '创作立项定稿',
    provider_profile_id: 'openai-compatible',
    model_settings: { model: 'gpt-4.1-mini', temperature: 0.7, max_tokens: 1800, top_p: 0.95, timeout_seconds: 120 },
    prompt_template_id: 'prompt-brief',
    input_schema: [
      { key: 'genre', label: '题材', type: 'select', required: true, default: '悬疑', options: ['悬疑', '都市'] },
      { key: 'word_target_soft', label: '目标字数', type: 'number', required: true, default: 100000 },
      { key: 'chapter_target_soft', label: '建议章数', type: 'number', required: true, default: 50 },
      { key: 'audience', label: '目标读者', type: 'text', required: true, default: '', placeholder: '例如：偏好强冲突、快节奏反转的悬疑读者' },
      { key: 'core_concept', label: '核心创意/冲突', type: 'textarea', required: true, default: '', hint: '立项只需要一个能撑起全书的核心冲突。', placeholder: '一句话说清冲突：谁+想要什么+被什么阻止' },
      { key: 'keywords', label: '关键词', type: 'tags', required: true, default: [], placeholder: '例如：孤岛、双时间线、身份互换' },
      { key: 'taboos', label: '禁忌/不要出现', type: 'textarea', required: true, default: '' },
    ],
  };
}

describe('StoryBriefFields length envelope', () => {
  it('renders hints under labels and placeholders inside empty controls', () => {
    const html = renderToStaticMarkup(<StoryBriefFields stage={briefStage()} onChange={() => undefined} />);

    expect(html).toContain('brief-field-hint');
    expect(html).toContain('立项只需要一个能撑起全书的核心冲突。');
    expect(html).toContain('一句话说清冲突：谁+想要什么+被什么阻止');
    expect(html).toContain('例如：偏好强冲突、快节奏反转的悬疑读者');
    // Tags fall back to the interaction cue only when no placeholder is provided.
    expect(html).toContain('例如：孤岛、双时间线、身份互换');
  });

  it('shows soft targets without inventing a fixed volume shape', () => {
    const html = renderToStaticMarkup(<StoryBriefFields stage={briefStage()} onChange={() => undefined} />);

    expect(html).toContain('目标字数');
    expect(html).toContain('建议章数');
    expect(html).toContain('软目标，不锁定故事边界');
    expect(html).not.toContain('合理下限');
    expect(html).not.toContain('合理上限');
    expect(html).not.toContain('卷 /');
  });
});
