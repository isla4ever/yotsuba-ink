import { ArrowLeft, BookMarked, BookOpen, Clock3, Compass, Database, Gauge, Globe2, Image, Layers, Lightbulb, Library, ListTree, Network, PackageCheck, PanelLeftClose, PanelLeftOpen, PenLine, ScrollText, Search, Settings, Sprout, type LucideIcon } from 'lucide-react';
import { memo, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { ControlTooltip } from './ControlTooltip';
import { ButtonLoadingIndicator } from './ButtonLoadingIndicator';
import { paletteShortcutHint } from './commandPaletteModel';
import { sidebarStageItems } from './workbenchSidebarModel';
import { bibleSectionMeta, bibleSections, defaultBibleSection, type BibleSection } from '../lib/stageRoutes';
import { nextSidebarFocusTarget } from '../lib/sidebarKeyboardNavigation';
import { useRunStateContext, useUICommandContext, useWorkflowConfigContext } from '../state/pipelineShellContext';

const stageIcons: Record<string, LucideIcon> = {
  brief: Lightbulb,
  spine: ScrollText,
  cast: Network,
  volumes: Library,
  detail: ListTree,
  text: PenLine,
  cover: Image,
  export: PackageCheck,
};

const bibleIcons: Record<BibleSection, LucideIcon> = {
  cast: Network,
  world: Globe2,
  foreshadow: Sprout,
  facts: Database,
};

function SidebarEntry({ collapsed, tooltip, children }: { collapsed: boolean; tooltip: string; children: ReactElement<{ 'aria-describedby'?: string }> }): ReactNode {
  return collapsed ? <ControlTooltip label={tooltip}>{children}</ControlTooltip> : children;
}

/** One console entry for modes that expose a run-wide monitor. */
function creationConsoleEntry({ activeRunId, openMonitor, policy, routePhase }: {
  activeRunId: string;
  openMonitor: () => void;
  policy: { monitor: 'none' | 'available' | 'default' };
  routePhase: string;
}) {
  const live = policy.monitor !== 'none' && activeRunId !== '';
  if (live) {
    return {
      current: routePhase === 'monitor',
      disabled: false,
      hint: '运行中：卷章结构、内容与日志同屏',
      live,
      open: openMonitor,
    };
  }
  return null;
}

/**
 * Memoized (Phase 12 F5): parent shell re-renders per run event, but this
 * sidebar only reads low-frequency context slices, so memo keeps it inert
 * while deltas stream.
 */
export const WorkbenchSidebar = memo(function WorkbenchSidebar() {
  const run = useRunStateContext();
  const { knowledgeDocuments, project, qualityMode, routePolicy, workflow } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  const navRef = useRef<HTMLElement | null>(null);
  const [templateState, setTemplateState] = useState<'idle' | 'saving' | 'saved'>('idle');

  if (!ui.sidebarVisible) return null;

  const expanded = ui.sidebarExpanded;
  const collapsed = !expanded;
  const runAvailable = run.activeRunId !== '';
  const stageItems = sidebarStageItems({
    policy: routePolicy,
    qualityMode,
    runHasStarted: runAvailable,
    stageRuntimes: run.stageRuntimes,
    stages: workflow.nodes,
  });
  const toggleLabel = expanded ? '收起侧栏' : '展开侧栏';
  const creationConsole = creationConsoleEntry({
    activeRunId: run.activeRunId,
    openMonitor: ui.openMonitor,
    policy: routePolicy,
    routePhase: run.routePhase,
  });
  const shortcutHint = paletteShortcutHint(typeof navigator === 'undefined' ? null : navigator);
  const knowledgeCount = knowledgeDocuments.length;
  const historyCount = run.historyItems.length;

  return (
    <nav
      aria-label="工作台侧栏"
      className={`workbench-sidebar ${expanded ? 'expanded' : 'collapsed'}`}
      onKeyDown={(event) => {
        const target = nextSidebarFocusTarget(navRef.current, event.key, document.activeElement);
        if (!target) return;
        event.preventDefault();
        target.focus();
      }}
      ref={navRef}
    >
      <div className="sidebar-project-header">
        <span aria-hidden="true" className="sidebar-project-accent" title={project ? project.title : undefined} />
        <div className="sidebar-project-title">
          <span className="sidebar-item-label">{project ? project.title : '未归档创作'}</span>
        </div>
        <div className="sidebar-project-tools">
          <SidebarEntry collapsed={collapsed} tooltip="返回工作室">
            <button aria-label="返回工作室" className="sidebar-project-back" onClick={ui.navigateStudio} title="返回作品工作室（运行会话保留）" type="button">
              <ArrowLeft size={14} />
            </button>
          </SidebarEntry>
          <SidebarEntry collapsed={collapsed} tooltip={toggleLabel}>
            <button aria-expanded={expanded} aria-label={toggleLabel} className="sidebar-project-back" onClick={ui.toggleSidebar} type="button">
              {expanded ? <PanelLeftClose size={14} /> : <PanelLeftOpen size={14} />}
            </button>
          </SidebarEntry>
        </div>
      </div>
      {project && expanded ? (
        <button
          className="workbench-sidebar-item sidebar-template-save"
          disabled={templateState === 'saving'}
          onClick={() => {
            setTemplateState('saving');
            void ui.saveWorkflowAsTemplate().then((name) => {
              setTemplateState(name ? 'saved' : 'idle');
              if (name) window.setTimeout(() => setTemplateState('idle'), 2400);
            });
          }}
          title="将当前作品工作流保存为可复用模板"
          type="button"
        >
          <span aria-hidden="true" className="sidebar-item-icon">{templateState === 'saving' ? <ButtonLoadingIndicator /> : <BookMarked size={16} />}</span>
          <span className="sidebar-item-label">
            {templateState === 'saving' ? '正在保存模板…' : templateState === 'saved' ? '已保存为模板' : '另存为模板'}
          </span>
        </button>
      ) : null}
      <SidebarEntry collapsed={collapsed} tooltip={`搜索 / 命令 · ${shortcutHint}`}>
        <button
          aria-haspopup="dialog"
          aria-keyshortcuts="Meta+K Control+K"
          className="workbench-sidebar-item workbench-sidebar-command"
          onClick={ui.openCommandPalette}
          title="打开全局命令面板"
          type="button"
        >
          <span aria-hidden="true" className="sidebar-item-icon"><Search size={16} /></span>
          <span className="sidebar-item-label">搜索 / 命令</span>
          <kbd aria-hidden="true" className="sidebar-item-kbd">{shortcutHint}</kbd>
        </button>
      </SidebarEntry>
      <p className="workbench-sidebar-heading" id="sidebar-stage-heading">{runAvailable ? '创作流程' : '作品准备'}</p>
      <div aria-labelledby="sidebar-stage-heading" className="workbench-sidebar-group" role="group">
        {creationConsole ? (
          <SidebarEntry collapsed={collapsed} tooltip={`创作控制台 · ${creationConsole.hint}`}>
            <button
              aria-current={creationConsole.current ? 'page' : undefined}
              className={`workbench-sidebar-item${creationConsole.current ? ' active' : ''}`}
              disabled={creationConsole.disabled}
              onClick={creationConsole.open}
              title={creationConsole.hint}
              type="button"
            >
              <span aria-hidden="true" className="sidebar-item-icon">{creationConsole.live ? <Gauge size={16} /> : <Layers size={16} />}</span>
              <span className="sidebar-item-label">创作控制台</span>
              <span aria-hidden="true" className={`sidebar-status-dot ${run.running ? 'running' : run.runHasStarted ? 'done' : 'idle'}`} />
            </button>
          </SidebarEntry>
        ) : null}
        {runAvailable && routePolicy.stageRoutes === 'all' ? stageItems.map((item) => {
          const Icon = stageIcons[item.id] ?? Layers;
          const current = run.routePhase === 'running' && run.routeStageId === item.id;
          return (
            <SidebarEntry collapsed={collapsed} key={item.id} tooltip={item.disabled ? `${item.label} · ${item.disabledReason}` : `${item.label} · ${item.statusLabel}`}>
              <button
                aria-current={current ? 'page' : undefined}
                className={`workbench-sidebar-item${current ? ' active' : ''}`}
                disabled={item.disabled}
                onClick={() => ui.navigateStage(item.id)}
                title={item.disabled ? item.disabledReason : `${item.statusLabel} · 打开阶段工作台`}
                type="button"
              >
                <span aria-hidden="true" className="sidebar-item-icon"><Icon size={16} /></span>
                <span className="sidebar-item-label">{item.label}</span>
                <span aria-hidden="true" className={`sidebar-status-dot ${item.status}`} />
                <span className="sidebar-visually-hidden">{item.statusLabel}</span>
              </button>
            </SidebarEntry>
          );
        }) : null}
      </div>
      {!runAvailable ? (
        <>
          <span aria-hidden="true" className="workbench-sidebar-separator" />
          <SidebarEntry collapsed={collapsed} tooltip="创作准备">
            <button
              aria-current={run.routePhase === 'planning' ? 'page' : undefined}
              className={`workbench-sidebar-item${run.routePhase === 'planning' ? ' active' : ''}`}
              onClick={ui.navigatePlanning}
              title="打开创作准备"
              type="button"
            >
              <span aria-hidden="true" className="sidebar-item-icon"><Compass size={16} /></span>
              <span className="sidebar-item-label">创作准备</span>
            </button>
          </SidebarEntry>
        </>
      ) : null}
      {!runAvailable || qualityMode === 'fast' ? null : qualityMode === 'balanced' ? (
        <>
          <span aria-hidden="true" className="workbench-sidebar-separator" />
          <SidebarEntry collapsed={collapsed} tooltip="Story Bible · 人物、世界观、伏笔与正典事实">
            <button
              aria-current={run.routePhase === 'bible' ? 'page' : undefined}
              className={`workbench-sidebar-item${run.routePhase === 'bible' ? ' active' : ''}`}
              onClick={() => ui.navigateBible(run.routeBibleSection || defaultBibleSection)}
              title="只读浏览设定：进入后在页内切换分区"
              type="button"
            >
              <span aria-hidden="true" className="sidebar-item-icon"><BookMarked size={16} /></span>
              <span className="sidebar-item-label">Story Bible</span>
            </button>
          </SidebarEntry>
        </>
      ) : (
      <>
      <span aria-hidden="true" className="workbench-sidebar-separator" />
      <p className="workbench-sidebar-heading" id="sidebar-bible-heading">Story Bible</p>
      <div aria-labelledby="sidebar-bible-heading" className="workbench-sidebar-group" role="group">
        {bibleSections.map((section) => {
          const Icon = bibleIcons[section];
          const meta = bibleSectionMeta[section];
          const current = run.routePhase === 'bible' && run.routeBibleSection === section;
          return (
            <SidebarEntry collapsed={collapsed} key={section} tooltip={`${meta.label} · ${meta.detail}`}>
              <button
                aria-current={current ? 'page' : undefined}
                className={`workbench-sidebar-item${current ? ' active' : ''}`}
                onClick={() => ui.navigateBible(section)}
                title={`只读浏览 · ${meta.detail}`}
                type="button"
              >
                <span aria-hidden="true" className="sidebar-item-icon"><Icon size={16} /></span>
                <span className="sidebar-item-label">{meta.label}</span>
              </button>
            </SidebarEntry>
          );
        })}
      </div>
      </>
      )}
      <span aria-hidden="true" className="workbench-sidebar-separator" />
      <div aria-label="全局入口" className="workbench-sidebar-group" role="group">
        <SidebarEntry collapsed={collapsed} tooltip="知识资料">
          <button aria-current={ui.knowledgeOpen ? 'page' : undefined} className={`workbench-sidebar-item${ui.knowledgeOpen ? ' active' : ''}`} onClick={ui.openKnowledge} title="管理项目资料与检索依据" type="button">
            <span aria-hidden="true" className="sidebar-item-icon"><BookOpen size={16} /></span>
            <span className="sidebar-item-label">知识资料</span>
            {knowledgeCount ? <span className="sidebar-item-badge">{knowledgeCount}</span> : null}
          </button>
        </SidebarEntry>
        <SidebarEntry collapsed={collapsed} tooltip="创作历史">
          <button aria-current={run.routePhase === 'history' ? 'page' : undefined} className={`workbench-sidebar-item${run.routePhase === 'history' ? ' active' : ''}`} onClick={ui.openHistory} title="查看运行、快照与导出版本" type="button">
            <span aria-hidden="true" className="sidebar-item-icon"><Clock3 size={16} /></span>
            <span className="sidebar-item-label">创作历史</span>
            {historyCount ? <span className="sidebar-item-badge">{historyCount}</span> : null}
          </button>
        </SidebarEntry>
        <SidebarEntry collapsed={collapsed} tooltip="模型与设置">
          <button aria-current={ui.settingsOpen ? 'page' : undefined} className={`workbench-sidebar-item${ui.settingsOpen ? ' active' : ''}`} onClick={ui.openSettings} title="编辑服务、模型和工作流偏好" type="button">
            <span aria-hidden="true" className="sidebar-item-icon"><Settings size={16} /></span>
            <span className="sidebar-item-label">模型与设置</span>
          </button>
        </SidebarEntry>
      </div>
    </nav>
  );
});
