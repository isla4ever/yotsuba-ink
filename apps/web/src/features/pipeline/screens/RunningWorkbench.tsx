import { StageRunWorkbench } from '../components/StageRunWorkbench';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../types/workflow';

type Props = {
  activeStage: WorkflowStage;
  approvalDraft: string;
  approvalPending: boolean;
  events: RunEvent[];
  memoryEvents: RunEvent[];
  workflow: WorkflowDefinition;
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => void;
  onRegenerateBrief: () => void;
};

export function RunningWorkbench(props: Props) {
  return <StageRunWorkbench {...props} />;
}
