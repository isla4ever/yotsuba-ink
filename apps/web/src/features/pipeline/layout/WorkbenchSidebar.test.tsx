import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { WorkbenchSidebar } from './WorkbenchSidebar';
import { PipelineShellTestProviders } from '../state/PipelineShellTestProviders';
import type { RunStateSlice, UICommandSlice, WorkflowConfigSlice } from '../state/pipelineShellContext';
import { modeRoutePolicy } from '../state/runPresentationState';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';

function renderSidebar(overrides: {
  runState?: Partial<RunStateSlice>;
  uiCommands?: Partial<UICommandSlice>;
  workflowConfig?: Partial<WorkflowConfigSlice>;
} = {}) {
  return renderToStaticMarkup(
    <PipelineShellTestProviders
      events={[runEvent('artifact.committed', { run_id: 'run-1', stage_id: 'brief', node_id: 'brief.commit_artifact', payload: {} })]}
      runState={{
        runHasStarted: true,
        routePhase: 'running',
        routeStageId: 'spine',
        ...overrides.runState,
      }}
      workflowConfig={{
        qualityMode: 'deep',
        routePolicy: modeRoutePolicy('deep', false),
        ...overrides.workflowConfig,
      }}
      uiCommands={overrides.uiCommands}
    >
      <WorkbenchSidebar />
    </PipelineShellTestProviders>,
  );
}

describe('WorkbenchSidebar', () => {
  it('renders nothing below the desktop breakpoint (<1024px)', () => {
    expect(renderSidebar({ uiCommands: { sidebarVisible: false } })).toBe('');
  });

  it('marks the current stage route and exposes real status plus global entries', () => {
    const html = renderSidebar();
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
    expect(html).toContain('sidebar-status-dot done');
    expect(html).toContain('知识资料');
    expect(html).toContain('创作历史');
    expect(html).toContain('模型与设置');
    expect(html).toContain('搜索 / 命令');
  });

  it('merges cockpit and monitor into one console entry alongside every stage workbench', () => {
    const html = renderSidebar({
      runState: { routePhase: 'planning', routeStageId: '' },
      workflowConfig: { qualityMode: 'balanced', routePolicy: modeRoutePolicy('balanced', true) },
    });
    expect(html).toContain('创作控制台');
    expect(html).not.toContain('创作驾驶舱');
    expect(html).not.toContain('全局监控台');
    expect(html).not.toContain('创作规划');
    // No attached run: the console opens the cockpit, so nothing is disabled.
    expect(html.match(/disabled=""/g) ?? []).toHaveLength(0);
    expect(html).toContain('人物圣经');
    expect(html).toContain('章节施工图');
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
  });

  it('condenses Story Bible to one entry in balanced mode and keeps the four sections in deep mode', () => {
    const balanced = renderSidebar({
      runState: { routePhase: 'planning', routeStageId: '' },
      workflowConfig: { qualityMode: 'balanced', routePolicy: modeRoutePolicy('balanced', true) },
    });
    expect(balanced).toContain('Story Bible');
    expect(balanced).not.toContain('伏笔账本');
    expect(renderSidebar()).toContain('伏笔账本');
  });

  it('marks the console entry current on the monitor route once a run is attached', () => {
    const html = renderSidebar({
      runState: { activeRunId: 'run-1', routePhase: 'monitor', routeStageId: '' },
      workflowConfig: { qualityMode: 'fast', routePolicy: modeRoutePolicy('fast', true) },
    });
    expect(html).toContain('创作控制台');
    expect(html).toContain('运行中：卷章结构、内容与日志同屏');
    const currentChunk = html.split('<button').find((chunk) => chunk.includes('aria-current="page"'));
    expect(currentChunk).toContain('创作控制台');
  });

  it('shows planning and all stages before a balanced run starts', () => {
    const html = renderSidebar({
      runState: { routePhase: 'planning', routeStageId: '', runHasStarted: false },
      workflowConfig: { qualityMode: 'balanced', routePolicy: modeRoutePolicy('balanced', false) },
    });
    expect(html).toContain('创作立项定稿');
    expect(html).toContain('创作规划');
    expect(html).not.toContain('创作驾驶舱');
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
  });

  it('always exposes the Story Bible section entries and marks the active section', () => {
    const html = renderSidebar({ runState: { routeBibleSection: 'foreshadow', routePhase: 'bible', routeStageId: '', runHasStarted: false } });
    for (const label of ['Story Bible', '人物关系', '世界观', '伏笔账本', '正典事实']) expect(html).toContain(label);
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
    const currentChunk = html.split('<button').find((chunk) => chunk.includes('aria-current="page"'));
    expect(currentChunk).toContain('伏笔账本');
    expect(currentChunk).not.toContain('disabled=""');
  });

  it('shows the project header with title, back-to-studio, and save-as-template when a project is active', () => {
    const html = renderSidebar({
      workflowConfig: {
        project: {
          id: 'proj-1',
          title: '雾城异闻',
          summary: '',
          accent_hue: 262,
          workflow_id: 'wf-proj-1',
          status: 'active',
          created_at: '',
          updated_at: '',
          latest_run_id: '',
        },
      },
    });
    expect(html).toContain('sidebar-project-header');
    expect(html).toContain('雾城异闻');
    expect(html).toContain('返回工作室');
    expect(html).toContain('另存为模板');
  });

  it('labels the unarchived legacy session and hides save-as-template without a project', () => {
    const html = renderSidebar();
    expect(html).toContain('未归档创作');
    expect(html).toContain('返回工作室');
    expect(html).not.toContain('另存为模板');
  });
});
