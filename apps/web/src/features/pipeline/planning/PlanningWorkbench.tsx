import '../../../styles/entry-planning.css';
import { KnowledgeWorldRail } from './KnowledgeWorldRail';
import { PipelineCanvas } from './PipelineCanvas';
import { StageInspector } from './StageInspector';
import type { CanvasLayout, InspectorTarget, KnowledgeDocument, RunEvent, SetupStep, WorkflowDefinition, WorkflowStage } from '../contracts';
import { AmbientSurface } from '../lib/visualEffects';
import { stageLabelForUi } from '../lib/display';
import { useEffect, useMemo, useRef, useState } from 'react';
import { PlanningStageConfigSheet } from './PlanningStageConfigSheet';
import { buildSetupSteps, shouldShowGuidedSetup } from '../lib/setupProgress';
import { useProviderReadinessContext } from '../settings/ProviderReadinessContext';
import type { SaveStatus } from '../state/useWorkflowAutosave';
import { GuidedSetupWorkbench } from './GuidedSetupWorkbench';
import { loadSetupDismissed, saveSetupDismissed } from './setupDismissalStorage';
import { activeCockpitStageId } from './cockpitRuntime';

type Props = {
  workflow: WorkflowDefinition;
  selectedId: string;
  selectedStage: WorkflowStage;
  events: RunEvent[];
  knowledgeDocuments: KnowledgeDocument[];
  onLayoutChange: (layout: CanvasLayout) => void;
  onCanvasSelect: (target: InspectorTarget) => void;
  onStageChange: (stage: WorkflowStage) => void;
  onAddModelOption: (providerId: string, model: string) => void;
  onOpenKnowledgeManager: () => void;
  onQualityModeChange: (mode: WorkflowDefinition['quality_mode']) => void;
  onRun: () => Promise<void>;
  onOpenStage: (stageId: string) => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
  runHasStarted: boolean;
  saveStatus: SaveStatus;
};

export function PlanningWorkbench({
  events,
  knowledgeDocuments,
  onAddModelOption,
  onCanvasSelect,
  onLayoutChange,
  onOpenKnowledgeManager,
  onQualityModeChange,
  onRun,
  onOpenStage,
  onStageChange,
  onWorkflowChange,
  runHasStarted,
  saveStatus,
  selectedId,
  selectedStage,
  workflow,
}: Props) {
  const [configSheetOpen, setConfigSheetOpen] = useState(false);
  // A11: the dismissal survives reloads per workflow; completion is re-derived.
  const [setupDismissed, setSetupDismissedState] = useState(() => loadSetupDismissed(workflow.id));
  const setSetupDismissed = (dismissed: boolean) => {
    setSetupDismissedState(dismissed);
    saveSetupDismissed(workflow.id, dismissed);
  };
  const [setupSessionActive, setSetupSessionActive] = useState<boolean | null>(null);
  useEffect(() => {
    setSetupDismissedState(loadSetupDismissed(workflow.id));
  }, [workflow.id]);
  const readiness = useProviderReadinessContext();
  const steps = useMemo(() => buildSetupSteps({
    knowledgeDocuments,
    readiness: readiness.status === 'ready' ? readiness.report : undefined,
    workflow,
  }), [knowledgeDocuments, readiness.report, readiness.status, workflow]);
  const needsSetup = shouldShowGuidedSetup(steps);
  const runtimeStageId = activeCockpitStageId(events, selectedId, workflow);
  const syncedRuntimeStageIdRef = useRef('');

  useEffect(() => {
    if (!runHasStarted) {
      syncedRuntimeStageIdRef.current = '';
      return;
    }
    if (syncedRuntimeStageIdRef.current === runtimeStageId) return;
    syncedRuntimeStageIdRef.current = runtimeStageId;
    if (runtimeStageId !== selectedId) onCanvasSelect({ kind: 'stage', id: runtimeStageId });
  }, [onCanvasSelect, runHasStarted, runtimeStageId, selectedId]);

  useEffect(() => {
    if (runHasStarted) {
      setSetupSessionActive(false);
      return;
    }
    if (readiness.status === 'idle' || readiness.status === 'loading') return;
    setSetupSessionActive((current) => {
      if (current === null) return needsSetup;
      return needsSetup ? true : current;
    });
  }, [needsSetup, readiness.status, runHasStarted]);

  if (!runHasStarted && (readiness.status === 'idle' || readiness.status === 'loading') && setupSessionActive === null) {
    return (
      <section className="setup-readiness-gate" aria-live="polite">
        <div className="setup-readiness-line" />
        <strong>正在确认项目准备状态</strong>
        <span>检查故事设定、项目资料和 AI 服务配置...</span>
      </section>
    );
  }

  if (!runHasStarted && setupSessionActive && !setupDismissed) {
    return (
      <GuidedSetupWorkbench
        knowledgeDocuments={knowledgeDocuments}
        readiness={readiness}
        saveStatus={saveStatus}
        steps={steps}
        workflow={workflow}
        onOpenKnowledgeManager={onOpenKnowledgeManager}
        onQualityModeChange={onQualityModeChange}
        onReadinessRefresh={readiness.refresh}
        onSaveAndExit={() => setSetupDismissed(true)}
        onStageChange={onStageChange}
        onStart={onRun}
        onWorkflowChange={onWorkflowChange}
      />
    );
  }
  return (
    <section className="workbench">
      <AmbientSurface className="planning-workbench-ambience" intensity="strong" />
      {!runHasStarted && needsSetup ? (
        <div className="setup-return-banner" role="status">
          <span><strong>首次准备尚未完成</strong><small>{setupReturnSummary(steps)}</small></span>
          <button className="tech-button" type="button" onClick={() => setSetupDismissed(false)}>继续准备</button>
        </div>
      ) : null}
      <section className="planning-primary-column">
        <PipelineCanvas
          events={events}
          onLayoutChange={onLayoutChange}
          onOpenStageConfig={() => setConfigSheetOpen(true)}
          onNodeDoubleClick={runHasStarted ? onOpenStage : undefined}
          onSelect={onCanvasSelect}
          selectedId={selectedId}
          workflow={workflow}
        />
        <KnowledgeWorldRail documents={knowledgeDocuments} events={events} onOpenKnowledge={onOpenKnowledgeManager} />
      </section>
      <PlanningStageConfigSheet onClose={() => setConfigSheetOpen(false)} open={configSheetOpen} stageLabel={stageLabelForUi(selectedStage)}>
        <StageInspector
          inputIdPrefix="planning-sheet"
          knowledgeDocuments={knowledgeDocuments}
          qualityMode={workflow.quality_mode}
          stage={selectedStage}
          providers={workflow.provider_profiles}
          onChange={onStageChange}
          onAddModelOption={onAddModelOption}
          onOpenKnowledgeManager={onOpenKnowledgeManager}
        />
      </PlanningStageConfigSheet>
    </section>
  );
}

/** A11 return banner: 第 N/3 步待完成 + 该步的真实概要。 */
function setupReturnSummary(steps: SetupStep[]) {
  const blockedIndex = steps.findIndex((step) => step.status === 'blocked');
  if (blockedIndex < 0) return steps[steps.length - 1]?.summary ?? '';
  const step = steps[blockedIndex];
  return `第 ${blockedIndex + 1}/${steps.length} 步（${step.label}）待完成 · ${step.summary}`;
}
