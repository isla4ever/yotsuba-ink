import { OctagonAlert, TriangleAlert } from 'lucide-react';
import { budgetAlertEqual, latestBudgetAlert } from '../lib/budgetStatus';
import {
  useRunEventsSelector,
  useRunStateContext,
  useUICommandContext,
  useWorkflowConfigContext,
} from '../state/pipelineShellContext';
import { canNavigateToStage } from '../state/runPresentationState';

/**
 * Phase 12 D5: persistent budget status bar under the header. Subscribes to
 * the run-events store (F5) for the latest budget event; offers the two real
 * exits — adjust the budget in settings, or export what already exists — and
 * never invents a new flow. Renders nothing while no budget event exists.
 */
export function BudgetStatusBar() {
  const alert = useRunEventsSelector((snapshot) => latestBudgetAlert(snapshot.events), budgetAlertEqual);
  const run = useRunStateContext();
  const { routePolicy, workflow } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  if (!alert) return null;

  const Icon = alert.severity === 'exceeded' ? OctagonAlert : TriangleAlert;
  const severityLabel = alert.severity === 'exceeded' ? '用量额度已用尽' : '用量额度预警';
  const stageLabel = alert.stageId ? workflow.nodes.find((stage) => stage.id === alert.stageId)?.label : '';
  const canOpenExport = run.runHasStarted && canNavigateToStage(routePolicy, 'export');

  return (
    <div className={`budget-status-bar ${alert.severity}`} role="status">
      <span aria-hidden="true" className="budget-status-icon"><Icon size={14} /></span>
      <p>
        <strong>{severityLabel}</strong>
        {stageLabel ? <em>{stageLabel}</em> : null}
        <span>{alert.message}</span>
      </p>
      <span className="budget-status-actions">
        <button onClick={ui.openSettings} type="button">调整预算</button>
        {canOpenExport ? (
          <button onClick={() => ui.navigateStage('export')} type="button">导出已有结果</button>
        ) : null}
      </span>
    </div>
  );
}
