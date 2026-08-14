import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { RunMonitorConsole } from './RunMonitorConsole';
import { defaultWorkflow } from '../../state/defaultWorkflow';
import { PipelineShellTestProviders } from '../../state/PipelineShellTestProviders';
import { runEvent } from '../../contracts/runEventTestFactory';
import type { RunEvent } from '../../contracts';

const events: RunEvent[] = [
  runEvent('node.started', { run_id: 'run-1', stage_id: 'spine', node_id: 'spine.generate', payload: {} }),
  runEvent('artifact.committed', { run_id: 'run-1', stage_id: 'brief', node_id: 'brief.commit_artifact', payload: {} }),
];

function renderConsole() {
  return renderToStaticMarkup(
    <PipelineShellTestProviders
      events={events}
      runState={{ activeRunId: 'run-1', routePhase: 'monitor', runHasStarted: true }}
      workflowConfig={{ qualityMode: 'fast' }}
    >
      <RunMonitorConsole
        activeRunId="run-1"
        events={events}
        qualityMode="fast"
        runControlState="running"
        stickyArtifacts={{ chapters: {}, stages: {} }}
        workflow={defaultWorkflow}
      />
    </PipelineShellTestProviders>,
  );
}

describe('RunMonitorConsole', () => {
  it('renders content and the run log on one screen instead of behind tabs', () => {
    const html = renderConsole();
    expect(html).toContain('monitor-main');
    expect(html).toContain('运行日志');
    expect(html).not.toContain('monitor-view-tab');
    expect(html).toContain('收起运行日志');
  });

  it('carries the shell rail entries so the console can own the sidebar slot', () => {
    const html = renderConsole();
    expect(html).toContain('monitor-sidebar');
    expect(html).toContain('返回工作室');
    expect(html).toContain('知识资料');
    expect(html).toContain('创作历史');
    expect(html).toContain('模型与设置');
  });
});
