/**
 * Phase 12 A11: "稍后继续" must survive reloads. The dismissal flag is stored
 * per workflow id, following the same key convention and failure semantics as
 * the state-layer scoped storage (`novel-workflow-*:{scope}`, try/catch with
 * in-memory fallback). Completion truth is always re-derived from the
 * workflow — this flag only records that the user chose to leave setup.
 */

const baseKey = 'novel-workflow-setup-dismissed';

export function setupDismissalKey(workflowId: string) {
  return `${baseKey}:${workflowId}`;
}

export function loadSetupDismissed(workflowId: string): boolean {
  try {
    return window.localStorage.getItem(setupDismissalKey(workflowId)) === '1';
  } catch {
    return false;
  }
}

export function saveSetupDismissed(workflowId: string, dismissed: boolean) {
  try {
    if (dismissed) window.localStorage.setItem(setupDismissalKey(workflowId), '1');
    else window.localStorage.removeItem(setupDismissalKey(workflowId));
  } catch {
    // The in-memory dismissal keeps working when persistence is unavailable.
  }
}
