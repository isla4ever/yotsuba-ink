import { useCallback, useEffect, useRef, useState, type Dispatch } from 'react';
import type { WorkflowStage } from '../contracts';
import type { RunAction } from './runReducer';
import { stageExists } from './runSelectors';

type SettlementTransition = {
  nextStageId?: string;
  stageId: string;
};

type ActiveSettlement = {
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
  const [settlement, setSettlementState] = useState<ActiveSettlement | null>(null);
  const settlementRef = useRef<ActiveSettlement | null>(null);
  const settlementClearTimer = useRef<number | null>(null);
  const stageNavigatorRef = useRef<(stageId: string) => void>(() => undefined);

  const setSettlement = useCallback((next: ActiveSettlement | null) => {
    settlementRef.current = next;
    setSettlementState(next);
  }, []);

  const clearSettlement = useCallback(() => {
    if (settlementClearTimer.current) window.clearTimeout(settlementClearTimer.current);
    settlementClearTimer.current = null;
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
    if (!current) return;
    if (settlementClearTimer.current) window.clearTimeout(settlementClearTimer.current);
    settlementClearTimer.current = null;
    setSettlement(null);
    if (current.nextStageId) navigateToStage(current.nextStageId);
  }, [navigateToStage, setSettlement]);

  const startSettlement = useCallback(({
    nextStageId = '',
    stageId,
  }: SettlementTransition) => {
    clearSettlement();
    setSettlement({ nextStageId, stageId });
    // A stage settlement remains readable until the user continues or the
    // four-second dwell completes, then route selection stays deterministic.
    settlementClearTimer.current = window.setTimeout(() => {
      settlementClearTimer.current = null;
      continueSettlement();
    }, SETTLEMENT_DWELL_MS);
  }, [clearSettlement, continueSettlement, setSettlement]);

  const reset = useCallback(() => {
    clearSettlement();
  }, [clearSettlement]);

  const setStageNavigator = useCallback((navigator: (stageId: string) => void) => {
    stageNavigatorRef.current = navigator;
  }, []);

  useEffect(() => () => {
    if (settlementClearTimer.current) window.clearTimeout(settlementClearTimer.current);
  }, []);

  return {
    clearSettlement,
    continueSettlement,
    navigateToStage,
    notifyStageNavigation,
    reset,
    setStageNavigator,
    settlementDwell: Boolean(settlement),
    settlementStageId: settlement?.stageId ?? '',
    startSettlement,
  };
}

export type RunTransitions = ReturnType<typeof useRunTransitions>;
