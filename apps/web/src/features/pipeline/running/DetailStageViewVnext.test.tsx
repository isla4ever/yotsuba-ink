// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DetailStageViewVnext } from './DetailStageViewVnext';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact = {
  chapters: [{
    id: 'chapter-1',
    number: 1,
    purpose: '取得档案',
    pov_character_id: 'char-lin',
    scenes: [{ id: 'scene-1', location: '档案室', goal: '取得登记簿', obstacle: '管理员拒绝', turn: '认出编号', outcome: '换得副本' }],
    obligations: [{ kind: 'character' as const, ref_id: 'char-lin', action: '承担调查决定' }],
    handoff: { unresolved_actions: [], emotional_carryover: [], next_pressure: '广播站开始清理档案' },
  }],
};

const options = [
  { id: 'char-lin', kind: 'character' as const, label: '林岚' },
  { id: 'thread-tape', kind: 'thread' as const, label: '追查母带' },
  { id: 'world-rule-1', kind: 'world_rule' as const, label: '广播覆盖个人记忆' },
  { id: 'ending-promise', kind: 'promise' as const, label: '真相最终公开' },
];

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

  it('allows obligations to select only frozen upstream references', () => {
    const onArtifactChange = vi.fn();
    act(() => root.render(<DetailStageViewVnext
      characters={[{ id: 'char-lin', name: '林岚' }]}
      obligationOptions={options}
      onArtifactChange={onArtifactChange}
      readOnly={false}
      result={JSON.stringify(artifact)}
    />));

    const reference = container.querySelector<HTMLSelectElement>('select[aria-label="义务引用"]');
    expect(reference?.options).toHaveLength(1);
    expect(reference?.options[0]?.value).toBe('char-lin');
    expect(container.querySelector('input[aria-label="义务引用"]')).toBeNull();

    const kind = container.querySelector<HTMLSelectElement>('select[aria-label="义务类型"]');
    act(() => {
      if (!kind) return;
      kind.value = 'promise';
      kind.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const changed = onArtifactChange.mock.calls[onArtifactChange.mock.calls.length - 1]?.[0];
    expect(changed.chapters[0].obligations[0]).toMatchObject({ kind: 'promise', ref_id: 'ending-promise' });
  });
});
