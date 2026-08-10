import { ArrowLeft, ArrowRight, LogOut, Play } from 'lucide-react';
import type { KnowledgeDocument, SetupStep, WorkflowDefinition, WorkflowStage } from '../contracts';
import type { SaveStatus as WorkflowSaveStatus } from '../state/useWorkflowAutosave';
import { useSetupFlow } from '../state/useSetupFlow';
import type { ProviderReadinessState } from '../settings/useProviderReadiness';
import { AiServiceSetupSection } from '../settings/AiServiceSetupSection';
import { SetupReviewSection } from './SetupReviewSection';
import { SetupStepNavigation } from './SetupStepNavigation';
import { StorySetupSection } from './StorySetupSection';

type Props = {
  knowledgeDocuments: KnowledgeDocument[];
  readiness: ProviderReadinessState;
  saveStatus: WorkflowSaveStatus;
  steps: SetupStep[];
  workflow: WorkflowDefinition;
  onOpenKnowledgeManager: () => void;
  onQualityModeChange: (mode: WorkflowDefinition['quality_mode']) => void;
  onReadinessRefresh: () => void;
  onSaveAndExit: () => void;
  onStageChange: (stage: WorkflowStage) => void;
  onStart: () => Promise<void>;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

const setupFormId = 'guided-setup-form';

export function GuidedSetupWorkbench({
  knowledgeDocuments,
  onOpenKnowledgeManager,
  onQualityModeChange,
  onReadinessRefresh,
  onSaveAndExit,
  onStageChange,
  onStart,
  onWorkflowChange,
  readiness,
  saveStatus,
  steps,
  workflow,
}: Props) {
  const setup = useSetupFlow(workflow.id, steps);
  const infoStage = workflow.nodes.find((stage) => stage.type === 'info');
  const activeIndex = steps.findIndex((step) => step.id === setup.flow.activeStepId);
  const onReview = setup.flow.activeStepId === 'review';
  const blocking = setup.currentStep?.issues.find((issue) => issue.severity === 'blocking');

  return (
    <section className="guided-setup-workbench">
      <header className="guided-setup-head">
        <div><p className="eyebrow">首次准备</p><h1>{workflow.name}</h1></div>
        <span className={`setup-save-state ${saveStatus}`}>{saveStatusLabel(saveStatus)}</span>
      </header>
      <div className="guided-setup-body">
        <SetupStepNavigation activeStepId={setup.flow.activeStepId} steps={steps} onStepRequest={setup.requestStep} />
        <div className="setup-form-workspace">
          {setup.flow.submitState === 'validating' && blocking ? (
            <div className="setup-error-summary" role="alert">{blocking.label}。已填写内容仍保留，请完成后继续。</div>
          ) : null}
          {/* E8: 表单包裹使文本字段回车即可前进；步骤切换后的焦点由 useSetupFlow 管理。 */}
          <form
            id={setupFormId}
            onSubmit={(event) => {
              event.preventDefault();
              if (onReview) void setup.start(onStart);
              else setup.continueFlow();
            }}
          >
            <div className="setup-step-panel" data-direction={setup.flow.direction} key={setup.flow.activeStepId}>
              {setup.flow.activeStepId === 'story' ? <StorySetupSection stage={infoStage} onChange={onStageChange} /> : null}
              {setup.flow.activeStepId === 'ai-service' ? (
                <AiServiceSetupSection readiness={readiness} workflow={workflow} onReadinessRefresh={onReadinessRefresh} onWorkflowChange={onWorkflowChange} />
              ) : null}
              {onReview ? (
                <SetupReviewSection
                  knowledgeDocuments={knowledgeDocuments}
                  stage={infoStage}
                  steps={steps}
                  workflow={workflow}
                  onOpenKnowledgeManager={onOpenKnowledgeManager}
                  onQualityModeChange={onQualityModeChange}
                  onStageChange={onStageChange}
                  onStepRequest={setup.requestStep}
                />
              ) : null}
            </div>
          </form>
        </div>
      </div>
      <footer className="guided-setup-actions">
        <button className="ghost" type="button" onClick={onSaveAndExit}><LogOut size={14} />稍后继续</button>
        <div>
          <button className="ghost" disabled={activeIndex <= 0} type="button" onClick={setup.back}><ArrowLeft size={14} />上一步</button>
          {onReview ? (
            <button className="tech-button" disabled={Boolean(blocking) || setup.flow.submitState === 'creating-run'} form={setupFormId} type="submit">
              <Play size={14} />{setup.flow.submitState === 'creating-run' ? '正在创建运行' : '开始创作'}
            </button>
          ) : (
            <button className="tech-button" form={setupFormId} type="submit">继续<ArrowRight size={14} /></button>
          )}
        </div>
      </footer>
    </section>
  );
}

function saveStatusLabel(status: WorkflowSaveStatus) {
  if (status === 'saving') return '正在自动保存';
  if (status === 'saved') return '已自动保存';
  if (status === 'failed') return '自动保存失败，草稿仍保留';
  return '等待修改';
}
