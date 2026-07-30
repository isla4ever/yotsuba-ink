import { CheckCircle2, ChevronDown, CircleAlert, FileOutput, ShieldCheck } from 'lucide-react';
import { InfoBriefEditor } from '../brief/InfoBriefEditor';
import type { KnowledgeDocument, ProviderProfile, QualityMode, WorkflowStage } from '../contracts';
import { stageLabelForUi } from '../lib/display';
import { stageArtifactLabel, stageConfigurationReadiness } from '../lib/planningReadiness';
import {
  coverAspectRatio,
  derivedQualitySummary,
  hiddenStageField,
  memoryPolicySummary,
} from '../lib/stageConfigurationPolicy';
import { updateStageInputDefault } from '../lib/stageConfig';
import { StageInputField } from './StageInputField';
import { StageModelSection, StageVariantCompareSection } from './StageVariantCompareSection';

type Props = {
  inputIdPrefix?: string;
  stage: WorkflowStage;
  qualityMode: QualityMode;
  providers: ProviderProfile[];
  knowledgeDocuments: KnowledgeDocument[];
  onChange: (stage: WorkflowStage) => void;
  onAddModelOption: (providerId: string, model: string) => void;
  onOpenKnowledgeManager?: () => void;
};

export function StageInspector({
  inputIdPrefix = 'stage-inspector',
  stage,
  qualityMode,
  providers,
  knowledgeDocuments,
  onChange,
  onAddModelOption,
  onOpenKnowledgeManager,
}: Props) {
  const readiness = stageConfigurationReadiness(stage);

  return (
    <aside aria-label={`${stageLabelForUi(stage)}阶段设置`} className="inspector">
      <div className="inspector-head">
        <div className="inspector-title-row">
          <div><p className="eyebrow">阶段设置</p><h2>{stageLabelForUi(stage)}</h2></div>
          <span className={`stage-readiness-badge ${readiness.ready ? 'ready' : 'incomplete'}`}>
            {readiness.ready ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}
            {readiness.ready ? '配置就绪' : `待补 ${readiness.missingLabels.length} 项`}
          </span>
        </div>
        <div className="stage-artifact-summary">
          <FileOutput size={15} /><span>阶段产物</span><strong>{stageArtifactLabel(stage)}</strong>
          <em>{readiness.total ? `${readiness.completed}/${readiness.total} 必填` : '无必填项'}</em>
        </div>
      </div>

      <section className="config-section stage-primary-fields">
        <div className="config-section-heading">
          <h3>{stage.type === 'info_recommend' ? '创作 Brief' : '阶段参数'}</h3>
          {readiness.total ? <span>{readiness.completed}/{readiness.total}</span> : null}
        </div>
        {stage.type === 'info_recommend' ? (
          <InfoBriefEditor
            idPrefix={inputIdPrefix}
            knowledgeDocuments={knowledgeDocuments}
            stage={stage}
            onChange={onChange}
            onOpenKnowledgeManager={onOpenKnowledgeManager}
          />
        ) : (
          <div className="stage-input-form">
            {stage.input_schema.filter((field) => !hiddenStageField(stage, field.key)).map((field) => (
              <StageInputField
                field={field}
                idPrefix={inputIdPrefix}
                key={field.key}
                onChange={(value) => onChange(updateStageInputDefault(stage, field.key, value))}
              />
            ))}
          </div>
        )}
        {stage.type === 'cover_image' ? <p className="stage-static-setting">画面比例 <strong>{coverAspectRatio(stage)}</strong> · 当前封面交付规范固定</p> : null}
      </section>

      <StageVariantCompareSection mode={qualityMode} stage={stage} onChange={onChange} />

      <details className="config-disclosure" key={stage.id}>
        <summary>
          <span>AI 服务与模型例外</span>
          <small>默认继承全局设置；只有本阶段需要不同模型时才调整</small>
          <ChevronDown size={15} />
        </summary>
        <div className="config-disclosure-body">
          <StageModelSection stage={stage} providers={providers} onAddModelOption={onAddModelOption} onChange={onChange} />
        </div>
      </details>

      <section aria-label="阶段规则" className="stage-policy-ledger">
        <div><ShieldCheck size={14} /><span><strong>质量方式由创作模式管理</strong><small>{derivedQualitySummary(stage, qualityMode)}</small></span></div>
        <div><FileOutput size={14} /><span><strong>设定读写由阶段合同管理</strong><small>{memoryPolicySummary(stage)}</small></span></div>
      </section>
      <p className="auto-save-hint">配置会自动保存，无需手动保存。</p>
    </aside>
  );
}
