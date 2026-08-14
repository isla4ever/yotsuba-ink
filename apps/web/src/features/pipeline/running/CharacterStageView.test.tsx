// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CharacterStageView } from './CharacterStageView';
import type { CharacterBibleArtifact } from './characterBibleArtifact';

vi.mock('./bible/CharacterNetwork3DView', () => ({
  CharacterNetwork3DView: ({ onSelectNode }: { onSelectNode: (id: string) => void }) => (
    <div className="mock-character-star-map">
      <button onClick={() => onSelectNode('subject-zhou')} type="button">角色节点</button>
      <button onClick={() => onSelectNode('subject-su-he')} type="button">历史主体节点</button>
    </div>
  ),
}));

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact: CharacterBibleArtifact = {
  subjects: [
    { id: 'subject-lin', name: '林岚', kind: 'protagonist', function: '追查母带来源', drive: '找回失踪母带', change: '接受记忆并不可靠', debut: 'chapter:1', limits: ['不会主动销毁原始记录'], demand_refs: ['demand-investigator'] },
    { id: 'subject-zhou', name: '周屿', kind: 'major', function: '提供相反证词', drive: '保护广播站', change: '承认自己的隐瞒', debut: 'chapter:2-3', limits: [], demand_refs: ['demand-witness'] },
    { id: 'subject-su-he', name: '前任档案员苏禾', kind: 'historical_record', function: '通过档案交付证据', drive: '保留原始记录', change: '以缺席证据改变当下判断', debut: 'chapter:1', limits: ['不得产生当下行动'], demand_refs: ['demand-record'] },
  ],
  relations: [{ a: 'subject-lin', b: 'subject-zhou', type: '互不信任的同盟', pressure: '母带公开期限' }],
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

  it('keeps ledger, focused dossier, relations and appearance projection together', () => {
    const source = JSON.stringify(artifact);
    act(() => root.render(<CharacterStageView onArtifactChange={() => undefined} readOnly={false} result={source} sourceResult={source} totalChapters={3} />));

    expect(container.querySelector('.character-roster-rail')).not.toBeNull();
    expect(container.querySelector('.character-dossier-editor')?.textContent).toContain('林岚');
    expect(container.querySelector('.character-neighborhood')?.textContent).toContain('周屿');
    expect(container.querySelector('.character-appearance-timeline')?.textContent).toContain('第 1 章');

    const relation = Array.from(container.querySelectorAll<HTMLButtonElement>('.character-neighborhood-list button'))[0];
    act(() => relation?.click());
    expect(container.querySelector<HTMLInputElement>('input[aria-label="主体姓名"]')?.value).toBe('周屿');
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

    act(() => Array.from(container.querySelectorAll<HTMLButtonElement>('.mock-character-star-map button'))
      .find((button) => button.textContent === '角色节点')?.click());
    expect(container.querySelector<HTMLInputElement>('input[aria-label="主体姓名"]')?.value).toBe('周屿');

    act(() => Array.from(container.querySelectorAll<HTMLButtonElement>('.mock-character-star-map button'))
      .find((button) => button.textContent === '历史主体节点')?.click());
    expect(container.querySelector<HTMLInputElement>('input[aria-label="主体姓名"]')?.value).toBe('前任档案员苏禾');
    expect(container.querySelector<HTMLSelectElement>('select[aria-label="主体类型"]')?.value).toBe('historical_record');
  });

  it('creates every subject kind with a contract-valid chapter window', () => {
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
    expect(withBoundedWindow.subjects[0]?.debut).toBe('chapter:3');

    act(() => container.querySelector<HTMLButtonElement>('button[aria-label="新增功能角色"]')?.click());
    const withFunctional = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0] as CharacterBibleArtifact;
    expect(withFunctional.subjects[withFunctional.subjects.length - 1]).toMatchObject({ kind: 'functional', debut: 'chapter:1' });

    act(() => container.querySelector<HTMLButtonElement>('button[aria-label="新增NPC"]')?.click());
    const withNpc = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0] as CharacterBibleArtifact;
    expect(withNpc.subjects[withNpc.subjects.length - 1]).toMatchObject({ kind: 'npc', debut: 'chapter:1' });

    act(() => container.querySelector<HTMLButtonElement>('button[aria-label="新增历史主体"]')?.click());
    const withHistorical = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0] as CharacterBibleArtifact;
    expect(withHistorical.subjects[withHistorical.subjects.length - 1]).toMatchObject({ kind: 'historical_record', debut: 'chapter:1' });
  });
});
