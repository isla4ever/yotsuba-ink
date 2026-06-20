import { StageRunWorkbench } from './StageRunWorkbench';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';

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
