import type { KnowledgeDocument, WorkflowStage } from '../contracts';
import { updateStageInputDefault } from '../lib/stageConfig';
import { NarrativeProfilePicker } from './NarrativeProfilePicker';
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
  const narrativeProfile = String(stage.input_schema.find((field) => field.key === 'narrative_profile')?.default ?? '故事建筑师');
  return (
    <div className="info-brief-editor">
      <StoryBriefFields idPrefix={idPrefix} stage={stage} onChange={onChange} />
      <NarrativeProfilePicker
        value={narrativeProfile}
        onChange={(value) => onChange(updateStageInputDefault(stage, 'narrative_profile', value))}
      />
      <ReferenceResearchPanel
        stage={stage}
        knowledgeDocuments={knowledgeDocuments}
        onChange={onChange}
        onOpenKnowledgeManager={onOpenKnowledgeManager}
      />
    </div>
  );
}
