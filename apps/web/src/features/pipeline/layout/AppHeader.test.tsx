import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ProviderReadinessProvider } from '../settings/ProviderReadinessContext';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { PipelineShellTestProviders } from '../state/PipelineShellTestProviders';
import { AppHeader } from './AppHeader';

vi.mock('./GlobalToolDock', () => ({ GlobalToolDock: () => null }));
vi.mock('./QualityModeTransitionOverlay', () => ({ MODE_NOTICE_DWELL_MS: 900, QualityModeTransitionOverlay: () => null }));

function renderHeader(runState: Parameters<typeof PipelineShellTestProviders>[0]['runState']) {
  return renderToStaticMarkup(
    <ProviderReadinessProvider enabled={false} workflowId={defaultWorkflow.id}>
      <PipelineShellTestProviders runState={runState}>
        <AppHeader sidebarVisible />
      </PipelineShellTestProviders>
    </ProviderReadinessProvider>,
  );
}

describe('AppHeader route semantics', () => {
  it('presents Story Bible as a read-only browse surface instead of the selected run stage', () => {
    const html = renderHeader({
      routeBibleSection: 'characters',
      routePhase: 'bible',
      runHasStarted: true,
      selectedStage: defaultWorkflow.nodes.find((stage) => stage.id === 'export') ?? defaultWorkflow.nodes[0],
      workspacePhase: 'running',
    });

    expect(html).toContain('人物关系');
    expect(html).toContain('Story Bible · 只读浏览');
    expect(html).not.toContain('导出产物');
  });

  it('uses the Yotsuba Ink product identity and keeps a real run stage visible', () => {
    const summary = defaultWorkflow.nodes.find((stage) => stage.id === 'summary') ?? defaultWorkflow.nodes[0];
    const html = renderHeader({
      routePhase: 'running',
      routeStageId: summary.id,
      runHasStarted: true,
      selectedStage: summary,
      workspacePhase: 'running',
    });

    expect(html).toContain('YI');
    expect(html).toContain('长篇创作工作台');
    expect(html).toContain(summary.label);
    expect(html).toContain('当前工作台');
  });
});
