import { useCallback, useEffect, useMemo, useState } from 'react';
import type { SetupFlowState, SetupStep, SetupStepId } from '../contracts';
import { firstBlockingSetupTarget, setupStepOrder } from '../lib/setupProgress';

const storagePrefix = 'novel-workflow-setup-last-step';

export function useSetupFlow(workflowId: string, steps: SetupStep[]) {
  const [flow, setFlow] = useState<SetupFlowState>(() => ({
    activeStepId: initialStepId(workflowId, steps),
    direction: 'none',
    submitState: 'idle',
  }));
  const activeIndex = setupStepOrder.indexOf(flow.activeStepId);

  const requestStep = useCallback((stepId: SetupStepId, fieldId?: string) => {
    setFlow((current) => ({
      ...current,
      activeStepId: stepId,
      direction: directionBetween(current.activeStepId, stepId),
      lastFocusedFieldId: fieldId,
      submitState: 'idle',
    }));
    saveLastStep(workflowId, stepId);
  }, [workflowId]);

  useEffect(() => {
    const blocking = firstBlockingSetupTarget(steps);
    if (!blocking) return;
    const blockingIndex = setupStepOrder.indexOf(blocking.stepId);
    if (blockingIndex >= activeIndex) return;
    requestStep(blocking.stepId, blocking.fieldId);
  }, [activeIndex, requestStep, steps]);

  useEffect(() => {
    const targetId = flow.lastFocusedFieldId ?? `setup-step-title-${flow.activeStepId}`;
    const frame = window.requestAnimationFrame(() => {
      const target = document.getElementById(targetId);
      if (target instanceof HTMLElement) target.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [flow.activeStepId, flow.lastFocusedFieldId]);

  const currentStep = useMemo(
    () => steps.find((step) => step.id === flow.activeStepId) ?? steps[0],
    [flow.activeStepId, steps],
  );

  const back = useCallback(() => {
    const index = setupStepOrder.indexOf(flow.activeStepId);
    if (index > 0) requestStep(setupStepOrder[index - 1]);
  }, [flow.activeStepId, requestStep]);

  const continueFlow = useCallback(() => {
    const blocking = currentStep?.issues.find((issue) => issue.severity === 'blocking');
    if (blocking) {
      setFlow((current) => ({ ...current, lastFocusedFieldId: blocking.target.fieldId, submitState: 'validating' }));
      focusField(blocking.target.fieldId ?? `setup-step-title-${blocking.target.stepId}`);
      return false;
    }
    const index = setupStepOrder.indexOf(flow.activeStepId);
    if (index < setupStepOrder.length - 1) requestStep(setupStepOrder[index + 1]);
    return true;
  }, [currentStep, flow.activeStepId, requestStep]);

  const start = useCallback(async (onStart: () => Promise<void>) => {
    const blocking = firstBlockingSetupTarget(steps);
    if (blocking) {
      requestStep(blocking.stepId, blocking.fieldId);
      setFlow((current) => ({ ...current, submitState: 'validating' }));
      return false;
    }
    setFlow((current) => ({ ...current, submitState: 'creating-run' }));
    try {
      await onStart();
      setFlow((current) => ({ ...current, submitState: 'idle' }));
      return true;
    } catch {
      setFlow((current) => ({ ...current, submitState: 'failed' }));
      return false;
    }
  }, [requestStep, steps]);

  return { back, continueFlow, currentStep, flow, requestStep, start };
}

function initialStepId(workflowId: string, steps: SetupStep[]): SetupStepId {
  const blocking = firstBlockingSetupTarget(steps)?.stepId;
  const stored = loadLastStep(workflowId);
  if (blocking && setupStepOrder.indexOf(blocking) < setupStepOrder.indexOf(stored)) return blocking;
  return stored;
}

function loadLastStep(workflowId: string): SetupStepId {
  try {
    const stored = window.localStorage.getItem(`${storagePrefix}:${workflowId}`);
    if (setupStepOrder.includes(stored as SetupStepId)) return stored as SetupStepId;
  } catch {
    // UI recovery is optional; business completion is always derived again.
  }
  return 'story';
}

function saveLastStep(workflowId: string, stepId: SetupStepId) {
  try {
    window.localStorage.setItem(`${storagePrefix}:${workflowId}`, stepId);
  } catch {
    // The current in-memory step remains usable when storage is unavailable.
  }
}

function directionBetween(current: SetupStepId, next: SetupStepId): SetupFlowState['direction'] {
  const delta = setupStepOrder.indexOf(next) - setupStepOrder.indexOf(current);
  return delta > 0 ? 'forward' : delta < 0 ? 'backward' : 'none';
}

function focusField(id: string) {
  window.requestAnimationFrame(() => {
    const target = document.getElementById(id);
    if (target instanceof HTMLElement) {
      target.focus({ preventScroll: false });
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
}
