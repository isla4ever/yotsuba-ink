import { BookOpen, Clock3, Layers, Library, Search, Settings } from 'lucide-react';
import { useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useRunStateContext, useUICommandContext } from '../../state/pipelineShellContext';
import { paletteShortcutHint } from '../commandPaletteModel';
import { studioKnowledgeRoute, studioSettingsRoute } from '../../lib/stageRoutes';
import { nextSidebarFocusTarget } from '../../lib/sidebarKeyboardNavigation';

/**
 * Studio Shell global sidebar: library anchors plus the existing global entry
 * callbacks (knowledge / history / settings). Rendered instead of the
 * per-project WorkbenchSidebar on the /studio route.
 */
export function StudioSidebar() {
  const run = useRunStateContext();
  const ui = useUICommandContext();
  const navRef = useRef<HTMLElement | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  if (!ui.sidebarVisible) return null;

  const shortcutHint = paletteShortcutHint(typeof navigator === 'undefined' ? null : navigator);
  const templateView = run.routePhase === 'studio' && new URLSearchParams(location.search).get('view') === 'templates';
  const libraryView = run.routePhase === 'studio' && !templateView;

  return (
    <nav
      aria-label="工作室侧栏"
      className="workbench-sidebar studio-sidebar expanded"
      onKeyDown={(event) => {
        const target = nextSidebarFocusTarget(navRef.current, event.key, document.activeElement);
        if (!target) return;
        event.preventDefault();
        target.focus();
      }}
      ref={navRef}
    >
      <div className="studio-sidebar-brand">
        <span aria-hidden="true" className="brand-mark">YI</span>
        <div>
          <p>Yotsuba Ink</p>
          <strong>作品工作室</strong>
        </div>
      </div>
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
      <p className="workbench-sidebar-heading" id="studio-sidebar-library-heading">工作室</p>
      <div aria-labelledby="studio-sidebar-library-heading" className="workbench-sidebar-group" role="group">
        <button aria-current={libraryView ? 'page' : undefined} className={`workbench-sidebar-item${libraryView ? ' active' : ''}`} onClick={() => navigate('/studio')} title="浏览全部作品" type="button">
          <span aria-hidden="true" className="sidebar-item-icon"><Library size={16} /></span>
          <span className="sidebar-item-label">作品库</span>
        </button>
        <button aria-current={templateView ? 'page' : undefined} className={`workbench-sidebar-item${templateView ? ' active' : ''}`} onClick={() => navigate('/studio?view=templates')} title="管理工作流模板" type="button">
          <span aria-hidden="true" className="sidebar-item-icon"><Layers size={16} /></span>
          <span className="sidebar-item-label">工作流模板</span>
        </button>
      </div>
      <span aria-hidden="true" className="workbench-sidebar-separator" />
      <div aria-label="全局入口" className="workbench-sidebar-group" role="group">
        <button aria-current={run.routePhase === 'studio-knowledge' ? 'page' : undefined} className={`workbench-sidebar-item${run.routePhase === 'studio-knowledge' ? ' active' : ''}`} onClick={() => navigate(studioKnowledgeRoute)} title="纵览全部作品的知识资料" type="button">
          <span aria-hidden="true" className="sidebar-item-icon"><BookOpen size={16} /></span>
          <span className="sidebar-item-label">知识资料</span>
        </button>
        <button aria-current={run.routePhase === 'history' ? 'page' : undefined} className={`workbench-sidebar-item${run.routePhase === 'history' ? ' active' : ''}`} onClick={ui.openHistory} title="查看运行、快照与导出版本" type="button">
          <span aria-hidden="true" className="sidebar-item-icon"><Clock3 size={16} /></span>
          <span className="sidebar-item-label">创作历史</span>
          {run.historyItems.length ? <span className="sidebar-item-badge">{run.historyItems.length}</span> : null}
        </button>
        <button aria-current={run.routePhase === 'studio-settings' ? 'page' : undefined} className={`workbench-sidebar-item${run.routePhase === 'studio-settings' ? ' active' : ''}`} onClick={() => navigate(studioSettingsRoute)} title="管理全局 AI 服务与默认模型" type="button">
          <span aria-hidden="true" className="sidebar-item-icon"><Settings size={16} /></span>
          <span className="sidebar-item-label">模型与设置</span>
        </button>
      </div>
    </nav>
  );
}
