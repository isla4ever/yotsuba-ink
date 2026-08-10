import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CommandPalette } from './CommandPalette';
import { PipelineShellTestProviders } from '../state/PipelineShellTestProviders';
import type { WorkflowConfigSlice } from '../state/pipelineShellContext';
import { modeRoutePolicy } from '../state/runPresentationState';
import type { RunEvent } from '../contracts';

function renderPalette(open: boolean, workflowConfig: Partial<WorkflowConfigSlice> = {}) {
  return renderToStaticMarkup(
    <PipelineShellTestProviders
      events={[{ type: 'node_completed', node_id: 'info' } as RunEvent]}
      runState={{
        runHasStarted: true,
      }}
      workflowConfig={{
        qualityMode: 'deep',
        routePolicy: modeRoutePolicy('deep', false),
        ...workflowConfig,
      }}
      uiCommands={{ commandPaletteOpen: open }}
    >
      <CommandPalette />
    </PipelineShellTestProviders>,
  );
}

describe('CommandPalette', () => {
  it('renders nothing while closed', () => {
    expect(renderPalette(false)).toBe('');
  });

  it('renders dialog + combobox/listbox semantics and points aria-activedescendant at the first enabled option', () => {
    const html = renderPalette(true);
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('role="listbox"');
    expect(html).toContain('role="combobox"');
    const activeDescendant = html.match(/aria-activedescendant="([^"]+)"/)?.[1];
    expect(activeDescendant).toBeTruthy();
    expect(activeDescendant).toContain('stage-info');
    const highlightedOption = html.split('<div').find((chunk) => chunk.includes(`id="${activeDescendant}"`));
    expect(highlightedOption).toContain('aria-selected="true"');
    for (const label of ['导航', '全局', '外观']) expect(html).toContain(`aria-label="${label}"`);
  });

  it('keeps every balanced stage command available', () => {
    const html = renderPalette(true, { qualityMode: 'balanced', routePolicy: modeRoutePolicy('balanced', false) });
    expect(html).not.toContain('平衡模式下后续阶段在驾驶舱内查看');
    expect(html).toContain('全书梗概');
    const activeDescendant = html.match(/aria-activedescendant="([^"]+)"/)?.[1];
    expect(activeDescendant).toContain('stage-info');
  });
});
