import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { PipelineShellTestProviders } from '../../state/PipelineShellTestProviders';
import { StudioSidebar } from './StudioSidebar';

function render(path: string, routePhase: 'studio' | 'history') {
  return renderToStaticMarkup(
    <StaticRouter location={path}>
      <PipelineShellTestProviders runState={{ routePhase }}>
        <StudioSidebar />
      </PipelineShellTestProviders>
    </StaticRouter>,
  );
}

describe('StudioSidebar', () => {
  it('keeps creation history inside the studio chrome and marks it active', () => {
    const html = render('/history', 'history');
    expect(html).toMatch(/aria-current="page"[^>]*>[^<]*<span[^>]*>.*创作历史/s);
    expect(html).toContain('作品工作室');
  });

  it('treats workflow templates as a real studio view', () => {
    const html = render('/studio?view=templates', 'studio');
    expect(html).toMatch(/aria-current="page"[^>]*>[^<]*<span[^>]*>.*工作流模板/s);
  });
});
