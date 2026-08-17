import '../../../styles/entry-planning.css';
import { useMemo } from 'react';
import type { KnowledgeDocument, WorkflowDefinition, WorkflowStage } from '../contracts';
import { buildSetupSteps } from '../lib/setupProgress';
import type { SaveStatus } from '../state/useWorkflowAutosave';
import { GuidedSetupWorkbench } from './GuidedSetupWorkbench';

type Props = {
  workflow: WorkflowDefinition;
  knowledgeDocuments: KnowledgeDocument[];
  onExit: () => void;
  onOpenKnowledgeManager: () => void;
  onQualityModeChange: (mode: WorkflowDefinition['quality_mode']) => void;
  onRun: () => Promise<void>;
  onStageChange: (stage: WorkflowStage) => void;
  saveStatus: SaveStatus;
};

/**
 * Pre-run launch gate. The stage chain and provider bindings are configured in
 * the workflow editor; once a run exists, routing leaves this surface entirely.
 */
export function PlanningWorkbench({
  knowledgeDocuments,
  onExit,
  onOpenKnowledgeManager,
  onQualityModeChange,
  onRun,
  onStageChange,
  saveStatus,
  workflow,
}: Props) {
  const steps = useMemo(() => buildSetupSteps({
    knowledgeDocuments,
    workflow,
  }), [knowledgeDocuments, workflow]);

  return (
    <GuidedSetupWorkbench
      knowledgeDocuments={knowledgeDocuments}
      saveStatus={saveStatus}
      steps={steps}
      workflow={workflow}
      onOpenKnowledgeManager={onOpenKnowledgeManager}
      onQualityModeChange={onQualityModeChange}
      onSaveAndExit={onExit}
      onStageChange={onStageChange}
      onStart={onRun}
    />
  );
}
