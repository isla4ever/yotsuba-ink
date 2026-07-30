import { Clock3, Settings } from 'lucide-react';
import { ControlTooltip } from './ControlTooltip';
import { RunResetControl } from './RunResetControl';
import { ThemeModeSwitch } from './ThemeModeSwitch';
import { useRunStateContext, useUICommandContext, useWorkflowConfigContext } from '../state/pipelineShellContext';

type Props = {
  /** Hidden when the persistent workbench sidebar already offers these entries (>=1024px). */
  showGlobalEntries: boolean;
};

export function GlobalToolDock({ showGlobalEntries }: Props) {
  const run = useRunStateContext();
  const { qualityMode } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  return (
    <div aria-label="全局工具" className="global-tool-dock" role="toolbar">
      <ControlTooltip label={ui.theme === 'dark' ? '切换日间模式' : '切换夜间模式'}>
        <ThemeModeSwitch onToggle={ui.toggleTheme} theme={ui.theme} />
      </ControlTooltip>
      {run.runHasStarted || run.resetUndoAvailable ? (
        <RunResetControl
          canReset={run.runHasStarted && !run.transitioning}
          canUndoReset={run.hasRunEvents}
          mode={qualityMode}
          onDismissUndo={ui.dismissResetUndo}
          onReset={ui.resetRun}
          onUndo={ui.undoResetRun}
          runId={run.activeRunId}
          undoAvailable={run.resetUndoAvailable}
        />
      ) : null}
      {showGlobalEntries ? (
        <>
          <ControlTooltip label="创作历史">
            <button
              aria-label="创作历史"
              aria-pressed={ui.historyOpen}
              className={`icon-button tech-icon-button dock-tool ${ui.historyOpen ? 'active' : ''}`}
              onClick={ui.openHistory}
              type="button"
            >
              <Clock3 size={16} />
            </button>
          </ControlTooltip>
          <ControlTooltip label="设置">
            <button
              aria-label="设置"
              aria-pressed={ui.settingsOpen}
              className={`icon-button tech-icon-button dock-tool ${ui.settingsOpen ? 'active' : ''}`}
              onClick={ui.openSettings}
              type="button"
            >
              <Settings size={16} />
            </button>
          </ControlTooltip>
        </>
      ) : null}
    </div>
  );
}
