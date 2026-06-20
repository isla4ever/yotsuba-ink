import { useState } from 'react';
import { BadgeCheck } from 'lucide-react';
import { InfoBriefEditor } from './InfoBriefEditor';
import { ModelOptionInput } from './ModelOptionInput';
import type { InputField, PromptTemplate, ProviderProfile, WorkflowStage } from '../types/workflow';
import { modelNameForUi, providerNameForUi } from '../utils/display';
import { addTagValue, clampQualityScore, coerceFieldValue, removeTagValue, updateStageInputDefault } from '../utils/stageConfig';

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
  const versionCompare = getField(stage, 'enable_version_compare');
  const versionCount = getField(stage, 'version_candidate_count');
  const judgeProvider = getField(stage, 'judge_provider_profile_id');
  const judgeModel = getField(stage, 'judge_model');
  const compareDimensions = getField(stage, 'compare_dimensions');
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
            {stage.input_schema.filter((field) => !hiddenStageField(stage, field)).map((field) => (
              <StageInputField
                field={field}
                key={field.key}
                onChange={(value) => onChange(updateStageInputDefault(stage, field.key, value))}
              />
            ))}
          </div>
        )}
      </section>

      <section className="config-section">
        <h3>模型 / API</h3>
        <div className="override-badge"><BadgeCheck size={13} />阶段覆盖</div>
        <label>
          Provider
          <select value={stage.provider_profile_id} onChange={(event) => {
            const provider = providers.find((item) => item.id === event.target.value);
            onChange({ ...stage, provider_profile_id: event.target.value, model_settings: { ...stage.model_settings, model: provider?.default_model ?? stage.model_settings.model } });
          }}>
            {providers.map((provider) => (
              <option value={provider.id} key={provider.id}>{providerNameForUi(provider)}</option>
            ))}
          </select>
        </label>
        <div className="settings-grid">
          <ModelOptionInput
            label="Model"
            providerId={stage.provider_profile_id}
            providers={providers}
            value={stage.model_settings.model}
            onAddOption={onAddModelOption}
            onChange={(model) => onChange({ ...stage, model_settings: { ...stage.model_settings, model } })}
          />
          <label>
            Temperature
            <input type="number" step="0.01" value={stage.model_settings.temperature} onChange={(event) => onChange({ ...stage, model_settings: { ...stage.model_settings, temperature: Number(event.target.value) } })} />
          </label>
          <label>
            Max Tokens
            <input type="number" value={stage.model_settings.max_tokens} onChange={(event) => onChange({ ...stage, model_settings: { ...stage.model_settings, max_tokens: Number(event.target.value) } })} />
          </label>
        </div>
      </section>

      <section className="config-section">
        <h3>Wiki / Memory</h3>
        <div className="toggle-row">
          <label><input type="checkbox" checked={stage.memory_policy.read} onChange={(event) => onChange({ ...stage, memory_policy: { ...stage.memory_policy, read: event.target.checked } })} />读取约束</label>
          <label><input type="checkbox" checked={stage.memory_policy.write} onChange={(event) => onChange({ ...stage, memory_policy: { ...stage.memory_policy, write: event.target.checked } })} />写回记忆</label>
        </div>
        <p className="muted">范围：{stage.memory_policy.scope} · {stage.memory_policy.kinds.join(' / ') || '无'}</p>
      </section>

      {stage.type === 'chapter_text' ? (
        <section className="config-section version-compare-section">
          <h3>自动版本比对</h3>
          <div className="toggle-row">
            <label>
              <input
                type="checkbox"
                checked={Boolean(versionCompare?.default)}
                onChange={(event) => onChange(updateField(stage, 'enable_version_compare', event.target.checked))}
              />
              开启多版本生成与评审
            </label>
          </div>
          <div className="settings-grid">
            <label>
              候选版本数
              <input
                type="number"
                min={2}
                max={5}
                value={Number(versionCount?.default ?? 3)}
                onChange={(event) => onChange(updateField(stage, 'version_candidate_count', Number(event.target.value)))}
              />
            </label>
            <label>
              评审 Provider
              <select
                value={String(judgeProvider?.default ?? 'inherit')}
                onChange={(event) => onChange(updateField(stage, 'judge_provider_profile_id', event.target.value))}
              >
                <option value="inherit">继承正文 Provider</option>
                {providers.map((provider) => (
                  <option value={provider.id} key={provider.id}>{providerNameForUi(provider)}</option>
                ))}
              </select>
            </label>
            <label>
              评审模型
              <input
                value={modelNameForUi(String(judgeModel?.default ?? 'mock-novel-judge'))}
                onChange={(event) => onChange(updateField(stage, 'judge_model', event.target.value))}
              />
            </label>
          </div>
          <div className="compare-dimensions">
            {(Array.isArray(compareDimensions?.default) ? compareDimensions.default : []).map((item) => (
              <span key={String(item)}>{String(item)}</span>
            ))}
          </div>
          <p className="cost-warning">多版本生成会按候选数放大 token 消耗，并额外调用评审模型；当前仅保存 UI 配置，后续接入真实生成与评审链路。</p>
        </section>
      ) : null}

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

function StageInputField({ field, onChange }: { field: InputField; onChange: (value: unknown) => void }) {
  const common = {
    id: `stage-input-${field.key}`,
    name: field.key,
  };

  return (
    <label className={field.type === 'textarea' ? 'stage-input-field wide' : 'stage-input-field'} htmlFor={common.id}>
      <span>
        {field.label}
        {field.required ? <b>必填</b> : null}
      </span>
      {field.type === 'select' ? (
        <select {...common} value={String(field.default ?? '')} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => <option value={option} key={option}>{option}</option>)}
        </select>
      ) : null}
      {field.type === 'textarea' ? (
        <textarea
          {...common}
          className="stage-input-textarea"
          value={String(field.default ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : null}
      {field.type === 'boolean' ? (
        <label className="inline-switch">
          <input
            checked={Boolean(field.default)}
            type="checkbox"
            onChange={(event) => onChange(event.target.checked)}
          />
          <span>{Boolean(field.default) ? '已开启' : '已关闭'}</span>
        </label>
      ) : null}
      {field.type !== 'select' && field.type !== 'textarea' && field.type !== 'boolean' ? (
        field.type === 'tags' ? (
          <TagInput field={field} onChange={onChange} />
        ) : (
          <input
            {...common}
            type={field.type === 'number' ? 'number' : 'text'}
            value={String(field.default ?? '')}
            onChange={(event) => onChange(coerceFieldValue(field, event.target.value))}
          />
        )
      ) : null}
      <small>{field.key} · {field.type}{field.help ? ` · ${field.help}` : ''}</small>
    </label>
  );
}

function TagInput({ field, onChange }: { field: InputField; onChange: (value: unknown) => void }) {
  const tags = Array.isArray(field.default) ? field.default.map(String) : [];
  const [draft, setDraft] = useState('');
  const commit = (raw: string) => {
    if (!raw.trim()) return;
    onChange(addTagValue(field.default, raw));
    setDraft('');
  };

  return (
    <div className="tag-input-box">
      <div className="tag-chip-row">
        {tags.map((tag) => (
          <button type="button" key={tag} onClick={() => onChange(removeTagValue(field.default, tag))}>
            {tag}<span>×</span>
          </button>
        ))}
      </div>
      <input
        value={draft}
        placeholder="输入后按回车添加"
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ',' || event.key === '，' || event.key === '、') {
            event.preventDefault();
            commit(draft);
          }
          if (event.key === 'Backspace' && !draft && tags.length) {
            onChange(tags.slice(0, -1));
          }
        }}
        onBlur={() => commit(draft)}
      />
    </div>
  );
}

function getField(stage: WorkflowStage, key: string) {
  return stage.input_schema.find((field) => field.key === key);
}

function hiddenStageField(stage: WorkflowStage, field: InputField) {
  return stage.type === 'chapter_text' && [
    'enable_version_compare',
    'version_candidate_count',
    'judge_provider_profile_id',
    'judge_model',
    'compare_dimensions',
  ].includes(field.key);
}

function updateField(stage: WorkflowStage, key: string, value: unknown): WorkflowStage {
  return {
    ...stage,
    input_schema: stage.input_schema.map((field) => (field.key === key ? { ...field, default: value } : field)),
  };
}
