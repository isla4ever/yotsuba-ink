import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { StoryBibleWorkbench } from './StoryBibleWorkbench';
import { bibleSections, type BibleSection } from '../../lib/stageRoutes';
import { PipelineShellTestProviders } from '../../state/PipelineShellTestProviders';

// force-graph requires a browser window at module scope; the canvas never mounts in these server-render tests.
vi.mock('react-force-graph-2d', () => ({ default: () => null }));

function renderBible(section: BibleSection) {
  return renderToStaticMarkup(
    <PipelineShellTestProviders runState={{ routeBibleSection: section, routePhase: 'bible' }}>
      <StoryBibleWorkbench section={section} />
    </PipelineShellTestProviders>,
  );
}

describe('StoryBibleWorkbench', () => {
  it('renders honest empty states for every section when no run data exists', () => {
    const expectations: Record<BibleSection, string> = {
      characters: '人物基线尚未建立',
      world: '世界观基线尚未建立',
      foreshadow: '伏笔账本为空',
      facts: '正典事实尚未写回',
    };
    for (const section of bibleSections) {
      const html = renderBible(section);
      expect(html, section).toContain(expectations[section]);
      expect(html, section).toContain('只读');
    }
  });

  it('marks the active section tab with aria-current and keeps all four tabs reachable', () => {
    const html = renderBible('world');
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
    const currentChunk = html.split('<button').find((chunk) => chunk.includes('aria-current="page"'));
    expect(currentChunk).toContain('世界观');
    for (const label of ['人物关系', '伏笔账本', '正典事实']) expect(html).toContain(label);
  });
});
