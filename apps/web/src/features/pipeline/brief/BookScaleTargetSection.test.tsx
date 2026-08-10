// @vitest-environment happy-dom

import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { WorkflowStage } from '../contracts';
import { BookScaleTargetSection } from './BookScaleTargetSection';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

function infoStage(): WorkflowStage {
  return {
    id: 'info',
    type: 'info',
    label: '创作立项定稿',
    provider_profile_id: 'openai-compatible',
    model_settings: { model: 'gpt-4.1-mini', temperature: 0.7, max_tokens: 1800, top_p: 0.95, timeout_seconds: 120 },
    prompt_template_id: 'prompt-info',
    input_schema: [
      { key: 'book_scale_target_mode', label: '成书目标', type: 'select', required: true, default: 'total_chars', options: ['total_chars', 'total_chapters'] },
      { key: 'book_scale_target_value', label: '目标值', type: 'number', required: true, default: 100000 },
    ],
  };
}

describe('BookScaleTargetSection interaction', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('updates the derived preview while keeping the target modes mutually exclusive', () => {
    function Harness() {
      const [stage, setStage] = useState(infoStage());
      return <BookScaleTargetSection idPrefix="scale-test" stage={stage} onChange={setStage} />;
    }

    act(() => root.render(<Harness />));
    const chapterMode = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent?.includes('总章数'));
    act(() => chapterMode?.click());

    const input = container.querySelector<HTMLInputElement>('#scale-test-book-scale-value');
    expect(input?.value).toBe('50');
    expect(container.textContent).toContain('4 卷 / 50 章');

    act(() => {
      if (input) {
        const setNativeValue = Object.getOwnPropertyDescriptor(
          HTMLInputElement.prototype,
          'value',
        )?.set;
        setNativeValue?.call(input, '20');
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });

    expect(container.textContent).toContain('4 万字');
    expect(container.textContent).toContain('2 卷 / 20 章');
    expect(container.textContent).toContain('10 / 10');
    expect(chapterMode?.getAttribute('aria-pressed')).toBe('true');
    expect(
      Array.from(container.querySelectorAll('button'))
        .find((button) => button.textContent?.includes('总字数'))
        ?.getAttribute('aria-pressed'),
    ).toBe('false');
  });
});
