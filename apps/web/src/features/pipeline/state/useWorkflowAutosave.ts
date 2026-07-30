import { useCallback, useEffect, useRef, useState } from 'react';
import type { WorkflowDefinition } from '../contracts';
import {
  createWorkflowAutosaveRevisionGate,
  createWorkflowAutosaveSuppressionGate,
  type WorkflowAutosaveRevisionGate,
  type WorkflowAutosaveSuppressionGate,
} from './workflowAutosave';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'failed';

type SaveWorkflow = (workflow: WorkflowDefinition) => Promise<void>;

export function useWorkflowAutosave(workflow: WorkflowDefinition, saveWorkflow: SaveWorkflow, enabled = true) {
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const suppressionGateRef = useRef<WorkflowAutosaveSuppressionGate<WorkflowDefinition> | null>(null);
  const revisionGateRef = useRef<WorkflowAutosaveRevisionGate | null>(null);
  const wasEnabledRef = useRef(false);
  if (!suppressionGateRef.current) {
    suppressionGateRef.current = createWorkflowAutosaveSuppressionGate<WorkflowDefinition>();
  }
  if (!revisionGateRef.current) revisionGateRef.current = createWorkflowAutosaveRevisionGate();

  useEffect(() => {
    if (!enabled) {
      wasEnabledRef.current = false;
      suppressionGateRef.current?.suppress(workflow);
      revisionGateRef.current?.invalidate();
      setSaveStatus('idle');
      return;
    }
    if (!wasEnabledRef.current) {
      wasEnabledRef.current = true;
      suppressionGateRef.current?.suppress(workflow);
    }
    if (suppressionGateRef.current?.shouldSuppress(workflow)) {
      revisionGateRef.current?.invalidate();
      setSaveStatus('idle');
      return;
    }
    const revision = revisionGateRef.current!.begin();
    setSaveStatus('saving');
    const timer = window.setTimeout(() => {
      void persistWorkflow(workflow, saveWorkflow, revision, revisionGateRef.current!, setSaveStatus);
    }, 800);
    return () => {
      window.clearTimeout(timer);
      revisionGateRef.current?.invalidate();
    };
  }, [enabled, saveWorkflow, workflow]);

  const suppressWorkflowSave = useCallback((hydratedWorkflow: WorkflowDefinition) => {
    suppressionGateRef.current?.suppress(hydratedWorkflow);
    revisionGateRef.current?.invalidate();
    setSaveStatus('idle');
  }, []);

  return { saveStatus, suppressWorkflowSave };
}

async function persistWorkflow(
  workflow: WorkflowDefinition,
  saveWorkflow: SaveWorkflow,
  revision: number,
  revisionGate: WorkflowAutosaveRevisionGate,
  setSaveStatus: (status: SaveStatus) => void,
) {
  try {
    await saveWorkflow(workflow);
    if (revisionGate.isCurrent(revision)) setSaveStatus('saved');
  } catch {
    if (revisionGate.isCurrent(revision)) setSaveStatus('failed');
  }
}
