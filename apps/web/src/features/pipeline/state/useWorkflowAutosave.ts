import { useEffect, useState } from 'react';
import type { WorkflowDefinition } from '../contracts';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'failed';

type SaveWorkflow = (workflow: WorkflowDefinition) => Promise<void>;

export function useWorkflowAutosave(workflow: WorkflowDefinition, saveWorkflow: SaveWorkflow) {
  const [booted, setBooted] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');

  useEffect(() => {
    if (!booted) {
      setBooted(true);
      return;
    }
    setSaveStatus('saving');
    const timer = window.setTimeout(() => {
      void persistWorkflow(workflow, saveWorkflow, setSaveStatus);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [booted, saveWorkflow, workflow]);

  return { saveStatus, setSaveStatus };
}

async function persistWorkflow(
  workflow: WorkflowDefinition,
  saveWorkflow: SaveWorkflow,
  setSaveStatus: (status: SaveStatus) => void,
) {
  try {
    await saveWorkflow(workflow);
    setSaveStatus('saved');
  } catch {
    setSaveStatus('failed');
  }
}
