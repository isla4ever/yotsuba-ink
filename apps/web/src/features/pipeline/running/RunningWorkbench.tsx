import '../../../styles/entry-running.css';
import { StageRunWorkbench } from './StageRunWorkbench';
import type { KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';

type Props = {
  activeRunId: string;
  activeStage: WorkflowStage;
  approvalDraft: string;
  approvalPending: boolean;
  events: RunEvent[];
  knowledgeDocuments: KnowledgeDocument[];
  memoryEvents: RunEvent[];
  settlementDwell: boolean;
  settlementStageId: string;
  workflow: WorkflowDefinition;
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onContinueSettlement: () => void;
  onOpenKnowledgeManager: () => void;
  onOpenWorkbench?: () => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
  onConfirmStageArtifact: (stageId: string, artifact?: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
};

export function RunningWorkbench(props: Props) {
  return <StageRunWorkbench {...props} />;
}
