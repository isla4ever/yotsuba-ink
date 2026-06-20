import { InfoBriefEditor } from '../brief/InfoBriefEditor';
import type { InputField, PromptTemplate, ProviderProfile, WorkflowStage } from '../contracts';
import { clampQualityScore, updateStageInputDefault } from '../lib/stageConfig';
import { StageInputField } from './StageInputField';
import { hiddenStageField, StageModelSection, StageVariantCompareSection } from './StageVariantCompareSection';

type Props = {
  stage: WorkflowStage;
  providers: ProviderProfile[];
  prompts: PromptTemplate[];
  onChange: (stage: WorkflowStage) => void;
  onAddModelOption: (providerId: string, model: string) => void;
  onKnowledgeDocumentsChanged?: () => void;
  onOpenKnowledgeManager?: () => void;
};

export function StageInspector({ stage, providers, prompts, onChange, onAddModelOption, onKnowledgeDocumentsChanged, onOpenKnowledgeManager }: Props) {
  void prompts;

  return (
    <aside className="inspector">
      <div className="inspector-head">
        <p className="eyebrow">Stage Inspector</p>
        <h2>{stage.label}</h2>
      </div>

      <section className="config-section">
        <h3>基础信息</h3>
        <label>
          阶段名称
          <input value={stage.label} onChange={(event) => onChange({ ...stage, label: event.target.value })} />
        </label>
        <label>
          输出 Key
          <input value={stage.output_key} onChange={(event) => onChange({ ...stage, output_key: event.target.value })} />
        </label>
      </section>

      <section className="config-section">
        <h3>用户入参</h3>
        {stage.type === 'info_recommend' ? (
          <InfoBriefEditor
            stage={stage}
            onChange={onChange}
            onKnowledgeDocumentsChanged={onKnowledgeDocumentsChanged}
            onOpenKnowledgeManager={onOpenKnowledgeManager}
          />
        ) : (
          <div className="stage-input-form">
            {stage.input_schema.filter((field) => !hiddenStageField(stage, field.key)).map((field) => (
              <StageInputField
                field={field}
                key={field.key}
                onChange={(value) => onChange(updateStageInputDefault(stage, field.key, value))}
              />
            ))}
          </div>
        )}
      </section>

      <StageModelSection stage={stage} providers={providers} onAddModelOption={onAddModelOption} onChange={onChange} />

      <section className="config-section">
        <h3>Wiki / Memory</h3>
        <div className="toggle-row">
          <label><input type="checkbox" checked={stage.memory_policy.read} onChange={(event) => onChange({ ...stage, memory_policy: { ...stage.memory_policy, read: event.target.checked } })} />读取约束</label>
          <label><input type="checkbox" checked={stage.memory_policy.write} onChange={(event) => onChange({ ...stage, memory_policy: { ...stage.memory_policy, write: event.target.checked } })} />写回记忆</label>
        </div>
        <p className="muted">范围：{stage.memory_policy.scope} · {stage.memory_policy.kinds.join(' / ') || '无'}</p>
      </section>

      <StageVariantCompareSection stage={stage} providers={providers} onChange={onChange} />

      <section className="config-section">
        <h3>质量策略</h3>
        <label>
          最低分
          <input
            type="number"
            min={stage.type === 'info_recommend' ? 0.6 : undefined}
            max={stage.type === 'info_recommend' ? 0.95 : undefined}
            step="0.01"
            value={stage.quality_policy.min_score}
            onChange={(event) => {
              const raw = Number(event.target.value);
              onChange({ ...stage, quality_policy: { ...stage.quality_policy, min_score: stage.type === 'info_recommend' ? clampQualityScore(raw) : raw } });
            }}
          />
        </label>
        {stage.quality_policy.checks.length ? (
          <div className="quality-check-chips">
            {stage.quality_policy.checks.map((check) => <span key={check}>{check}</span>)}
          </div>
        ) : null}
        <div className="toggle-row">
          <label><input type="checkbox" checked={stage.quality_policy.retry_on_fail} onChange={(event) => onChange({ ...stage, quality_policy: { ...stage.quality_policy, retry_on_fail: event.target.checked } })} />失败重试</label>
          <label><input type="checkbox" checked={stage.quality_policy.require_human_review} onChange={(event) => onChange({ ...stage, quality_policy: { ...stage.quality_policy, require_human_review: event.target.checked } })} />人工确认</label>
        </div>
      </section>
      <p className="auto-save-hint">配置会自动保存，无需手动保存。</p>
    </aside>
  );
}
