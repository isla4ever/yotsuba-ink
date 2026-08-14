import { useCallback, useEffect, useRef, useState, type Dispatch } from 'react';
import type { WorkflowStage } from '../contracts';
import type { RunAction } from './runReducer';
import { stageExists } from './runSelectors';

/**
 * Settlement kinds (Phase 12 D7):
 * - `route`: dwellable settlement on stage-route surfaces — stays until the
 *   user hits 「继续」 or the 4s auto-continue elapses (progress ring).
 * - `cockpit_auto`: fast/balanced cockpit auto-advance — never blocks; the
 *   cockpit shows an expandable settlement summary card instead.
 * - `balanced_cockpit`: the balanced brief-to-cockpit hand-off.
 */
type SettlementTransition = {
  kind: 'balanced_cockpit' | 'cockpit_auto' | 'route';
  nextStageId?: string;
  stageId: string;
};

type ActiveSettlement = {
  kind: SettlementTransition['kind'];
  nextStageId: string;
  stageId: string;
};

export const SETTLEMENT_DWELL_MS = 4000;

export function useRunTransitions({
  dispatchRun,
  stages,
}: {
  dispatchRun: Dispatch<RunAction>;
  stages: WorkflowStage[];
}) {
  const [automationCockpitReady, setAutomationCockpitReady] = useState(false);
  const [settlement, setSettlementState] = useState<ActiveSettlement | null>(null);
  const settlementRef = useRef<ActiveSettlement | null>(null);
  const settlementClearTimer = useRef<number | null>(null);
  const settlementNavigateTimer = useRef<number | null>(null);
  const stageNavigatorRef = useRef<(stageId: string) => void>(() => undefined);

  const setSettlement = useCallback((next: ActiveSettlement | null) => {
    settlementRef.current = next;
    setSettlementState(next);
  }, []);

  const clearSettlement = useCallback(() => {
    if (settlementClearTimer.current) window.clearTimeout(settlementClearTimer.current);
    if (settlementNavigateTimer.current) window.clearTimeout(settlementNavigateTimer.current);
    settlementClearTimer.current = null;
    settlementNavigateTimer.current = null;
    setSettlement(null);
  }, [setSettlement]);

  const notifyStageNavigation = useCallback((stageId: string) => {
    stageNavigatorRef.current(stageId);
  }, []);

  const navigateToStage = useCallback((stageId: string) => {
    if (!stageExists(stages, stageId)) return;
    dispatchRun({ type: 'stage_selected', stageId });
    notifyStageNavigation(stageId);
  }, [dispatchRun, notifyStageNavigation, stages]);

  /** Completes the dwellable route settlement (user 「继续」 or 4s auto). */
  const continueSettlement = useCallback(() => {
    const current = settlementRef.current;
    if (!current || current.kind !== 'route') return;
    if (settlementClearTimer.current) window.clearTimeout(settlementClearTimer.current);
    settlementClearTimer.current = null;
    setSettlement(null);
    if (current.nextStageId) navigateToStage(current.nextStageId);
  }, [navigateToStage, setSettlement]);

  const startSettlement = useCallback(({
    kind,
    nextStageId = '',
    stageId,
  }: SettlementTransition) => {
    clearSettlement();
    setSettlement({ kind, nextStageId, stageId });
    if (kind === 'route') {
      // Phase 12 D7: dwell — user-driven continue with a 4s auto-continue.
      settlementClearTimer.current = window.setTimeout(() => {
        settlementClearTimer.current = null;
        continueSettlement();
      }, SETTLEMENT_DWELL_MS);
      return;
    }
    if (kind === 'balanced_cockpit') {
      setAutomationCockpitReady(true);
      settlementNavigateTimer.current = window.setTimeout(() => {
        dispatchRun({ type: 'stage_selected', stageId: nextStageId || 'spine' });
      }, 900);
    } else if (nextStageId && stageExists(stages, nextStageId)) {
      settlementNavigateTimer.current = window.setTimeout(() => navigateToStage(nextStageId), 900);
    }
    settlementClearTimer.current = window.setTimeout(() => {
      setSettlement(null);
      settlementClearTimer.current = null;
      settlementNavigateTimer.current = null;
    }, 1200);
  }, [clearSettlement, continueSettlement, dispatchRun, navigateToStage, setSettlement, stages]);

  const reset = useCallback(() => {
    clearSettlement();
    setAutomationCockpitReady(false);
  }, [clearSettlement]);

  const setStageNavigator = useCallback((navigator: (stageId: string) => void) => {
    stageNavigatorRef.current = navigator;
  }, []);

  useEffect(() => () => {
    if (settlementClearTimer.current) window.clearTimeout(settlementClearTimer.current);
    if (settlementNavigateTimer.current) window.clearTimeout(settlementNavigateTimer.current);
  }, []);

  return {
    automationCockpitReady,
    clearSettlement,
    continueSettlement,
    navigateToStage,
    notifyStageNavigation,
    reset,
    setAutomationCockpitReady,
    setStageNavigator,
    /** True when the active settlement is the dwellable route kind. */
    settlementDwell: settlement?.kind === 'route',
    settlementStageId: settlement?.stageId ?? '',
    startSettlement,
  };
}

export type RunTransitions = ReturnType<typeof useRunTransitions>;
