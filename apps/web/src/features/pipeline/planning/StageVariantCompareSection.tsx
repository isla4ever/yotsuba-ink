import { BadgeCheck } from 'lucide-react';
import { ModelOptionInput } from '../settings/fields/ModelOptionInput';
import type { ProviderProfile, WorkflowStage } from '../contracts';
import { modelNameForUi, providerNameForUi } from '../lib/display';

type Props = {
  stage: WorkflowStage;
  providers: ProviderProfile[];
  onAddModelOption: (providerId: string, model: string) => void;
  onChange: (stage: WorkflowStage) => void;
};

export function StageModelSection({ stage, providers, onAddModelOption, onChange }: Props) {
  return (
    <section className="config-section">
      <h3>模型 / API</h3>
      <div className="override-badge"><BadgeCheck size={13} />阶段覆盖</div>
      <label>
        Provider
        <select value={stage.provider_profile_id} onChange={(event) => {
          const provider = providers.find((item) => item.id === event.target.value);
          onChange({
            ...stage,
            provider_profile_id: event.target.value,
            model_settings: { ...stage.model_settings, model: provider?.default_model ?? stage.model_settings.model },
          });
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
  );
}

export function StageVariantCompareSection({ stage, providers, onChange }: Omit<Props, 'onAddModelOption'>) {
  if (stage.type !== 'chapter_text') return null;

  const versionCompare = getField(stage, 'enable_version_compare');
  const versionCount = getField(stage, 'version_candidate_count');
  const judgeProvider = getField(stage, 'judge_provider_profile_id');
  const judgeModel = getField(stage, 'judge_model');
  const compareDimensions = getField(stage, 'compare_dimensions');

  return (
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
  );
}

export function hiddenStageField(stage: WorkflowStage, fieldKey: string) {
  return stage.type === 'chapter_text' && [
    'enable_version_compare',
    'version_candidate_count',
    'judge_provider_profile_id',
    'judge_model',
    'compare_dimensions',
  ].includes(fieldKey);
}

function getField(stage: WorkflowStage, key: string) {
  return stage.input_schema.find((field) => field.key === key);
}

function updateField(stage: WorkflowStage, key: string, value: unknown): WorkflowStage {
  return {
    ...stage,
    input_schema: stage.input_schema.map((field) => (field.key === key ? { ...field, default: value } : field)),
  };
}
