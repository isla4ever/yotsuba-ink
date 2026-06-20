import { InsightRail } from './InsightRail';
import { KnowledgeWorldRail } from './KnowledgeWorldRail';
import { PipelineCanvas } from './PipelineCanvas';
import { RuntimeLayerInspector } from './RuntimeLayerInspector';
import { StageInspector } from './StageInspector';
import type { CanvasLayout, InspectorTarget, KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';

type Props = {
  workflow: WorkflowDefinition;
  selectedId: string;
  selectedStage: WorkflowStage;
  selectedInspectorTarget: InspectorTarget;
  events: RunEvent[];
  knowledgeDocuments: KnowledgeDocument[];
  onLayoutChange: (layout: CanvasLayout) => void;
  onCanvasSelect: (target: InspectorTarget) => void;
  onStageChange: (stage: WorkflowStage) => void;
  onAddModelOption: (providerId: string, model: string) => void;
  onKnowledgeDocumentsChanged: () => Promise<void>;
  onOpenKnowledgeManager: () => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export function PlanningWorkbench({
  events,
  knowledgeDocuments,
  onAddModelOption,
  onCanvasSelect,
  onKnowledgeDocumentsChanged,
  onLayoutChange,
  onOpenKnowledgeManager,
  onStageChange,
  onWorkflowChange,
  selectedId,
  selectedInspectorTarget,
  selectedStage,
  workflow,
}: Props) {
  return (
    <section className="workbench">
      <section className="canvas-column">
        <PipelineCanvas workflow={workflow} selectedId={selectedId} events={events} onLayoutChange={onLayoutChange} onSelect={onCanvasSelect} />
      </section>
      <KnowledgeWorldRail documents={knowledgeDocuments} events={events} onOpenKnowledge={onOpenKnowledgeManager} />
      <InsightRail workflow={workflow} events={events} />
      {selectedInspectorTarget.kind === 'stage' ? (
        <StageInspector
          stage={selectedStage}
          providers={workflow.provider_profiles}
          prompts={workflow.prompt_templates}
          onChange={onStageChange}
          onAddModelOption={onAddModelOption}
          onKnowledgeDocumentsChanged={onKnowledgeDocumentsChanged}
          onOpenKnowledgeManager={onOpenKnowledgeManager}
        />
      ) : (
        <RuntimeLayerInspector kind={selectedInspectorTarget.kind} workflow={workflow} onWorkflowChange={onWorkflowChange} />
      )}
    </section>
  );
}
