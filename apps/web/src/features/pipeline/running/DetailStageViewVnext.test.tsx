// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DetailStageViewVnext } from './DetailStageViewVnext';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact = {
  chapters: [{
    ref: 'chapter-1',
    volume_ref: 'volume-1',
    purpose: '取得档案',
    pov: 'subject-lin',
    cast_ids: ['subject-lin'],
    scenes: [{ place: '档案室', objective: '取得登记簿', conflict: '管理员拒绝', turn: '认出编号', result: '换得副本' }],
    handoff: '广播站开始清理档案',
  }],
};

describe('DetailStageViewVnext', () => {
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

  it('keeps POV references frozen and edits the compact scene contract', () => {
    const onArtifactChange = vi.fn();
    act(() => root.render(<DetailStageViewVnext
      characters={[{ id: 'subject-lin', name: '林岚' }, { id: 'subject-zhou', name: '周屿' }]}
      onArtifactChange={onArtifactChange}
      readOnly={false}
      result={JSON.stringify(artifact)}
    />));

    const povGroup = container.querySelector('[aria-label="POV"]');
    const povChips = Array.from(povGroup?.querySelectorAll<HTMLButtonElement>('button') ?? []);
    expect(povChips.map((chip) => chip.textContent)).toEqual(['林岚', '周屿']);
    expect(povChips[0]?.getAttribute('aria-pressed')).toBe('true');
    expect(container.textContent).toContain('volume-1 · chapter-1');
    expect(container.textContent).not.toContain('义务');

    const castGroup = container.querySelector('[aria-label="本章出场人物"]');
    const supporting = Array.from(castGroup?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('周屿'));
    act(() => supporting?.click());
    expect(onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0].chapters[0].cast_ids).toEqual(['subject-lin', 'subject-zhou']);

    const place = container.querySelector<HTMLInputElement>('input[aria-label="场景地点"]');
    act(() => {
      if (!place) return;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(place, '封存库');
      place.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const changed = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0];
    expect(changed.chapters[0].volume_ref).toBe('volume-1');
    expect(changed.chapters[0].scenes[0]).toMatchObject({ place: '封存库', objective: '取得登记簿', conflict: '管理员拒绝', turn: '认出编号', result: '换得副本' });
  });
});
