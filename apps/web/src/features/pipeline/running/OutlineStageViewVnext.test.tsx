// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { OutlineStageViewVnext } from './OutlineStageViewVnext';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const artifact = {
  volumes: [{
    id: 'volume-1',
    chapter_window: 'chapter:1-3',
    objective: '找到失踪母带',
    turns: [{ id: 'turn-1', event: '找到副本', consequence: '广播站开始追捕' }],
    ending_state: '林岚带着副本离开港区',
    character_windows: [{ character_id: 'char-lin', entry_state: '独自调查', exit_state: '接受合作', turn_id: 'turn-1' }],
    thread_windows: [],
  }],
};

describe('OutlineStageViewVnext', () => {
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

  it('projects the frozen BookScalePlan window without an editable field', () => {
    act(() => root.render(<OutlineStageViewVnext
      characters={[{ id: 'char-lin', name: '林岚' }]}
      onArtifactChange={() => undefined}
      readOnly={false}
      result={JSON.stringify(artifact)}
      volumeWindows={['chapter:1-3']}
    />));

    expect(container.querySelector('.vnext-readonly-projection output')?.textContent).toBe('chapter:1-3');
    expect(container.querySelector('input[value="chapter:1-3"]')).toBeNull();
  });
});
