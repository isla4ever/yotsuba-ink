// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CharacterStageView } from './CharacterStageView';
import type { CharacterBibleArtifact } from './characterBibleArtifact';

vi.mock('./bible/CharacterNetwork3DView', () => ({
  CharacterNetwork3DView: ({ onSelectNode }: { onSelectNode: (id: string) => void }) => (
    <button className="mock-character-star-map" onClick={() => onSelectNode('character-2')} type="button">星图节点</button>
  ),
}));

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact: CharacterBibleArtifact = {
  characters: [
    {
      id: 'character-1',
      name: '林岚',
      tier: 'protagonist',
      narrative_function: '追查母带来源',
      external_goal: '找回失踪母带',
      inner_need: '接受记忆并不可靠',
      arc: { start: '确信记录', turning_point: '发现剪辑', end: '公开真相' },
      first_appearance_window: 'chapter:1',
      hard_boundaries: ['不会主动销毁原始记录'],
    },
    {
      id: 'character-2',
      name: '周屿',
      tier: 'major',
      narrative_function: '提供相反证词',
      external_goal: '保护广播站',
      inner_need: '承认自己的隐瞒',
      arc: { start: '回避', turning_point: '交出副本', end: '出庭作证' },
      first_appearance_window: 'chapter:2-3',
      hard_boundaries: [],
    },
  ],
  relationships: [{
    source_id: 'character-1',
    target_id: 'character-2',
    nature: '互不信任的同盟',
    initial_state: '相互试探',
    pressure: '母带公开期限',
  }],
  npc_slots: [{ id: 'npc-slot-1', function: '交付档案', first_appearance_window: 'chapter:1', limits: ['不得解决主冲突'] }],
};

describe('CharacterStageView orchestration workbench', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      addEventListener: vi.fn(),
      matches: query.includes('max-width'),
      media: query,
      onchange: null,
      removeEventListener: vi.fn(),
    }));
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('keeps ledger, focused dossier, relations, arc and appearance projection together', () => {
    const source = JSON.stringify(artifact);
    act(() => root.render(<CharacterStageView onArtifactChange={() => undefined} readOnly={false} result={source} sourceResult={source} totalChapters={3} />));

    expect(container.querySelector('.character-roster-rail')).not.toBeNull();
    expect(container.querySelector('.character-dossier-editor')?.textContent).toContain('林岚');
    expect(container.querySelector('.character-neighborhood')?.textContent).toContain('周屿');
    expect(container.querySelector('.character-arc-track')).not.toBeNull();
    expect(container.querySelector('.character-appearance-timeline')?.textContent).toContain('第 1 章');

    const relation = Array.from(container.querySelectorAll<HTMLButtonElement>('.character-neighborhood-list button'))[0];
    act(() => relation?.click());
    expect(container.querySelector<HTMLInputElement>('input[aria-label="角色姓名"]')?.value).toBe('周屿');
  });

  it('uses the star map as a browsing projection and keeps selection synchronized', async () => {
    const source = JSON.stringify(artifact);
    act(() => root.render(<CharacterStageView onArtifactChange={() => undefined} readOnly={false} result={source} sourceResult={source} totalChapters={3} />));

    const starMapButton = Array.from(container.querySelectorAll<HTMLButtonElement>('.character-bible-view-toggle button'))
      .find((button) => button.textContent?.includes('星图'));
    await act(async () => starMapButton?.click());
    await act(async () => undefined);
    expect(container.querySelector('.character-bible-star-layout')).not.toBeNull();
    expect(container.querySelector('.mock-character-star-map')).not.toBeNull();

    act(() => container.querySelector<HTMLButtonElement>('.mock-character-star-map')?.click());
    expect(container.querySelector<HTMLInputElement>('input[aria-label="角色姓名"]')?.value).toBe('周屿');
  });

  it('creates new roles and NPC slots with a contract-valid chapter window', () => {
    const source = JSON.stringify(artifact);
    const onArtifactChange = vi.fn();
    act(() => root.render(<CharacterStageView onArtifactChange={onArtifactChange} readOnly={false} result={source} sourceResult={source} totalChapters={3} />));

    const appearanceStart = container.querySelector<HTMLInputElement>('input[aria-label="首次出现窗口最早章节"]');
    expect(appearanceStart?.max).toBe('3');
    act(() => {
      if (!appearanceStart) return;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(appearanceStart, '4');
      appearanceStart.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const withBoundedWindow = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0] as CharacterBibleArtifact;
    expect(withBoundedWindow.characters[0]?.first_appearance_window).toBe('chapter:3');

    act(() => container.querySelector<HTMLButtonElement>('button[aria-label="新增功能角色"]')?.click());
    const withCharacter = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0] as CharacterBibleArtifact;
    expect(withCharacter.characters[withCharacter.characters.length - 1]?.first_appearance_window).toBe('chapter:1');

    act(() => Array.from(container.querySelectorAll<HTMLButtonElement>('.character-section-command')).find((button) => button.textContent?.includes('新增槽位'))?.click());
    const withNpc = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0] as CharacterBibleArtifact;
    expect(withNpc.npc_slots[withNpc.npc_slots.length - 1]?.first_appearance_window).toBe('chapter:1');
  });
});
