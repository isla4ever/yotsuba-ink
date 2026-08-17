// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VolumeStageView } from './VolumeStageView';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact = {
  volumes: [{
    id: 'volume-1',
    title: '雾港残响',
    promise: '找到失踪母带的来源',
    conflict: '广播站封锁证据',
    climax: '在全港广播原始录音',
    climax_turn_ref: 'turn-1',
    closure: '林岚接受共同作证',
    turn_refs: ['turn-1'],
    cast_ids: ['subject-lin'],
    length_hint: 'short' as const,
  }],
};

describe('VolumeStageView', () => {
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

  it('edits complete-story volume contracts and only references frozen cast', () => {
    const onArtifactChange = vi.fn();
    act(() => root.render(<VolumeStageView
      characters={[{ id: 'subject-lin', name: '林岚' }, { id: 'subject-zhou', name: '周屿' }]}
      onArtifactChange={onArtifactChange}
      readOnly={false}
      result={JSON.stringify(artifact)}
    />));

    expect(container.textContent).toContain('本卷承诺');
    expect(container.textContent).toContain('核心冲突');
    expect(container.textContent).toContain('高潮');
    expect(container.textContent).toContain('闭合');
    expect(container.textContent).not.toContain('chapter_window');
    expect(container.textContent).not.toContain('BookScale');

    const castGroup = container.querySelector('[aria-label="本卷相关人物"]');
    const castToggle = Array.from(castGroup?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('周屿'));
    expect(castToggle?.getAttribute('aria-pressed')).toBe('false');
    act(() => castToggle?.click());
    expect(onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0].volumes[0].cast_ids).toEqual(['subject-lin', 'subject-zhou']);
  });
});
