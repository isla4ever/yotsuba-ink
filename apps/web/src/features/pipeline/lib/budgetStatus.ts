import type { RunEvent } from '../contracts';

/**
 * Phase 12 D5: persistent budget status derived from the real backend events
 * `stage_budget_warning` / `run_budget_warning` / `stage_budget_exceeded` /
 * `run_budget_exceeded` / `manual_intervention_required` (budget-carrying).
 * The newest budget event wins; copy is composed locally in writer language
 * (「用量额度」, never "Token") instead of relaying raw backend messages.
 */

export type BudgetAlert = {
  severity: 'warning' | 'exceeded';
  scope: 'stage' | 'run';
  stageId: string;
  message: string;
  usedTokens: number | null;
  maxTokens: number | null;
};

const budgetEventTypes = new Set([
  'manual_intervention_required',
  'run_budget_exceeded',
  'run_budget_warning',
  'stage_budget_exceeded',
  'stage_budget_warning',
]);

export function latestBudgetAlert(events: RunEvent[]): BudgetAlert | null {
  const index = events.findIndex((item) => (
    budgetEventTypes.has(item.type)
    // Manual interventions count only when budget-triggered (they carry the snapshot).
    && (item.type !== 'manual_intervention_required' || Boolean(item.budget_state))
  ));
  if (index < 0) return null;
  const event = events[index];
  const severity = event.type.endsWith('_warning') ? 'warning' as const : 'exceeded' as const;
  if (severity === 'exceeded') {
    // A newer resume means the creator already adjusted the budget and moved
    // on — a stale 「已用尽」 bar would contradict the running state.
    const resumeIndex = events.findIndex((item) => (
      item.type === 'run_resumed' || item.type === 'run_checkpoint_recovery_requested'
    ));
    if (resumeIndex >= 0 && resumeIndex < index) return null;
  }
  const scope = event.type.startsWith('stage_') || (event.type === 'manual_intervention_required' && event.node_id)
    ? 'stage' as const
    : 'run' as const;
  return {
    maxTokens: numberOrNull(event.max_tokens),
    message: alertMessage(severity, scope, numberOrNull(event.used_tokens), numberOrNull(event.max_tokens)),
    scope,
    severity,
    stageId: event.node_id ?? '',
    usedTokens: numberOrNull(event.used_tokens),
  };
}

export function budgetAlertEqual(left: BudgetAlert | null, right: BudgetAlert | null): boolean {
  if (left === right) return true;
  if (!left || !right) return false;
  return left.severity === right.severity
    && left.scope === right.scope
    && left.stageId === right.stageId
    && left.message === right.message
    && left.usedTokens === right.usedTokens
    && left.maxTokens === right.maxTokens;
}

function alertMessage(
  severity: 'warning' | 'exceeded',
  scope: 'stage' | 'run',
  used: number | null,
  max: number | null,
): string {
  const scopeLabel = scope === 'run' ? '本次运行' : '当前阶段';
  const ratio = used != null && max ? `（已用 ${Math.min(100, Math.round((used / max) * 100))}%）` : '';
  if (severity === 'warning') return `${scopeLabel}的用量额度即将用完${ratio}，可调整预算或先导出已有结果。`;
  return `${scopeLabel}的用量额度已用尽，创作已在安全点暂停。请调整预算或导出已有结果。`;
}

function numberOrNull(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}
