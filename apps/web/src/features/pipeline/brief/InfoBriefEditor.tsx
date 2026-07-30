import type { KnowledgeDocument, WorkflowStage } from '../contracts';
import { ReferenceResearchPanel } from './ReferenceResearchPanel';
import { StoryBriefFields } from './StoryBriefFields';

type Props = {
  idPrefix?: string;
  stage: WorkflowStage;
  knowledgeDocuments: KnowledgeDocument[];
  onOpenKnowledgeManager?: () => void;
  onChange: (stage: WorkflowStage) => void;
};

export function InfoBriefEditor({ idPrefix = 'brief', stage, knowledgeDocuments, onChange, onOpenKnowledgeManager }: Props) {
  return (
    <div className="info-brief-editor">
      <StoryBriefFields idPrefix={idPrefix} stage={stage} onChange={onChange} />
      <ReferenceResearchPanel
        stage={stage}
        knowledgeDocuments={knowledgeDocuments}
        onChange={onChange}
        onOpenKnowledgeManager={onOpenKnowledgeManager}
      />
    </div>
  );
}
