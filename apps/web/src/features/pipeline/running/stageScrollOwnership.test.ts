import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function source(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), 'utf8');
}

describe('stage workbench scroll ownership', () => {
  it('exposes semantic artifact and runtime scroll regions', () => {
    expect(source('./StageRunMain.tsx')).toContain('data-scroll-region="artifact"');
    expect(source('./StageRunMainArea.tsx')).not.toContain('data-scroll-region="artifact"');
    expect(source('./RuntimeInsights.tsx')).toContain("data-scroll-region={panelKeys.length ? 'runtime' : 'context'}");
  });

  it('gives desktop artifacts vertical scroll and mobile layouts page scroll', () => {
    const layout = source('../../../styles/stage-run-layout.css');
    const adaptive = source('../../../styles/stage-run-adaptive-layout.css');

    expect(layout).toMatch(/\.stage-run-main > \[data-scroll-region="artifact"\]\s*\{[^}]*min-height: 0;[^}]*overflow-x: hidden;[^}]*overflow-y: auto;/s);
    expect(layout).toMatch(/\[data-scroll-region="context"\]\s*\{[^}]*min-height: 0;[^}]*overflow-x: hidden;[^}]*overflow-y: auto;/s);
    expect(layout).toContain('.product-shell .stage-run-workbench > .stage-run-main > [data-scroll-region="artifact"],');
    expect(layout).toContain('overflow: visible;');
    expect(adaptive).toContain('.product-shell .stage-run-workbench > .stage-run-main.text-main > [data-scroll-region="artifact"]');
    expect(adaptive).not.toContain('grid-row: 2');
  });

  it('keeps the decision tray in artifact flow while pinning it to the visible edge', () => {
    const finalize = source('../../../styles/stage-run-finalize-stability.css');

    expect(finalize).toMatch(/\.stage-decision-slot\s*\{[^}]*bottom: 0;[^}]*position: sticky;/s);
    expect(finalize).not.toMatch(/\.stage-decision-slot\s*\{[^}]*position: absolute;/s);
  });
});
