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
    title: '档案余烬',
    target_characters: 3000,
    turn_refs: ['turn-1'],
    purpose: '取得档案',
    pov: 'subject-lin',
    cast_ids: ['subject-lin'],
    scenes: [
      { place: '档案室', objective: '取得登记簿', conflict: '管理员拒绝', turn: '认出编号', result: '换得副本' },
      { place: '旧潮道', objective: '转移副本', conflict: '出口被封', turn: '找到暗门', result: '带走副本' },
    ],
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
      characters={[
        { id: 'subject-lin', kind: 'protagonist', name: '林岚' },
        { id: 'subject-zhou', kind: 'major', name: '周屿' },
        { id: 'subject-record', kind: 'historical_record', name: '旧档记录者' },
      ]}
      onArtifactChange={onArtifactChange}
      readOnly={false}
      result={JSON.stringify(artifact)}
      sceneRange={[1, 6]}
    />));

    const povGroup = container.querySelector('[aria-label="POV"]');
    const povChips = Array.from(povGroup?.querySelectorAll<HTMLButtonElement>('button') ?? []);
    expect(povChips.map((chip) => chip.textContent)).toEqual(['林岚', '周屿', '旧档记录者']);
    expect(povChips[0]?.getAttribute('aria-pressed')).toBe('true');
    expect(povChips[2]?.disabled).toBe(true);
    expect(container.textContent).toContain('volume-1 · chapter-1');
    expect(container.textContent).toContain('正文预算 3,000 字');
    expect(container.textContent).toContain('动态区间 1-6');
    expect(container.textContent).not.toContain('义务');

    const castGroup = container.querySelector('[aria-label="本章出场人物"]');
    const supporting = Array.from(castGroup?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('周屿'));
    const historical = Array.from(castGroup?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('旧档记录者'));
    expect(historical?.disabled).toBe(true);
    expect(historical?.title).toContain('不能作为 POV');
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

    const removeScene = container.querySelector<HTMLButtonElement>('button[aria-label="删除场景"]');
    act(() => removeScene?.click());
    expect(onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0].chapters[0].scenes).toHaveLength(1);
    expect(container.querySelector('button[aria-label="删除场景"]')).toBeNull();

    const addScene = Array.from(container.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent?.includes('新增场景'));
    act(() => addScene?.click());
    expect(onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0].chapters[0].scenes).toHaveLength(2);
  });
});
