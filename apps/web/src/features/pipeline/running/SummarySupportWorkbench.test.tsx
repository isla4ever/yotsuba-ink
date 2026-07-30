// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { SummarySupportWorkbench } from './SummarySupportWorkbench';
import { summaryArtifact } from './stageArtifacts';
import { summaryInfoBaseline } from './summaryArtifactModel';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('SummarySupportWorkbench', () => {
  let container: HTMLDivElement;
  let root: ReturnType<typeof createRoot>;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('keeps structure and turning points reachable through one compact responsive view switch', () => {
    act(() => {
      root.render(
        <SummarySupportWorkbench
          artifact={summaryArtifact(JSON.stringify({
            act_structure: [{ goal: '找到母带', title: '起', turn: '听见未来' }],
            character_arcs: [],
            key_turns: [{ detail: '时间标记成立', label: '预知确认' }],
          }))}
          baseline={summaryInfoBaseline('')}
          onOpenArc={() => undefined}
          onOpenArcs={() => undefined}
          onOpenBeat={() => undefined}
          onOpenTurn={() => undefined}
          readOnly
        />,
      );
    });

    const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>('.summary-support-tabs button'));
    const [beats, turns] = buttons;
    expect(buttons).toHaveLength(2);
    expect(beats?.getAttribute('aria-pressed')).toBe('true');
    expect(turns?.getAttribute('aria-pressed')).toBe('false');

    act(() => turns?.click());
    expect(beats?.getAttribute('aria-pressed')).toBe('false');
    expect(turns?.getAttribute('aria-pressed')).toBe('true');
  });
});
