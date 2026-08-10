import { BadgeCheck, RotateCcw } from 'lucide-react';
import type { ProviderProfile, WorkflowStage } from '../contracts';
import { modelNameForUi } from '../lib/display';
import {
  clampTemperature,
  coverImageQuality,
  temperaturePresetFor,
  temperaturePresets,
} from '../lib/stageConfigurationPolicy';
import { resetStageProviderException, stageHasProviderException, stageProviderSummary } from '../lib/stageProviderException';
import { ModelOptionInput } from '../settings/fields/ModelOptionInput';
import { OptionField } from '../settings/fields/OptionField';
import { providerOptionItems } from '../settings/providerOptionItems';

type Props = {
  stage: WorkflowStage;
  providers: ProviderProfile[];
  onAddModelOption: (providerId: string, model: string) => void;
  onChange: (stage: WorkflowStage) => void;
};

export function StageModelSection({ stage, providers, onAddModelOption, onChange }: Props) {
  const textProviders = providers.filter((provider) => provider.kind === 'openai-compatible');
  const imageProviders = providers.filter((provider) => provider.kind === 'openai-compatible-image');
  const imageProvider = imageProviders.find((provider) => provider.id === stage.image_provider_profile_id) ?? imageProviders[0];
  const hasException = stageHasProviderException(stage, providers);
  const activeTemperaturePreset = temperaturePresetFor(stage.model_settings.temperature);
  const imageQuality = coverImageQuality(stage);

  return (
    <section className="config-section stage-provider-exception">
      <div className="stage-exception-head">
        <span><h3>AI 服务与模型例外</h3><small>{stageProviderSummary(stage, providers)}</small></span>
        <div className={hasException ? 'override-badge active' : 'override-badge'}>
          <BadgeCheck size={13} />{hasException ? '本阶段已覆盖' : '继承全局设置'}
        </div>
      </div>
      {hasException ? (
        <button className="ghost stage-exception-reset" type="button" onClick={() => onChange(resetStageProviderException(stage, providers))}>
          <RotateCcw size={13} />恢复继承
        </button>
      ) : null}
      <OptionField
        label={stage.type === 'cover' ? '封面规划文本服务' : '文本生成服务'}
        options={providerOptionItems(textProviders)}
        value={stage.provider_profile_id}
        onValueChange={(providerId) => {
          const provider = textProviders.find((item) => item.id === providerId);
          const nextModel = provider?.default_model ?? stage.model_settings.model;
          onChange({
            ...stage,
            provider_profile_id: providerId,
            model_settings: { ...stage.model_settings, model: nextModel },
          });
        }}
      />
      {stage.type === 'cover' ? (
        <OptionField
          label="封面生成服务"
          options={providerOptionItems(imageProviders)}
          status={imageProvider ? 'ready' : 'warning'}
          statusText={imageProvider ? `图片模型 ${modelNameForUi(imageProvider.default_model)}` : '尚未连接图片服务'}
          value={stage.image_provider_profile_id ?? ''}
          onValueChange={(providerId) => onChange({ ...stage, image_provider_profile_id: providerId })}
        />
      ) : null}
      <ModelOptionInput
        label="阶段生成模型"
        providerId={stage.provider_profile_id}
        providers={providers}
        value={stage.model_settings.model}
        onAddOption={onAddModelOption}
        onChange={(model) => onChange({
          ...stage,
          model_settings: { ...stage.model_settings, model },
        })}
      />
      <div className="stage-temperature-control">
        <span>创作发散度</span>
        <div aria-label="创作发散度" className="stage-temperature-segments" role="group">
          {temperaturePresets.map((preset) => (
            <button
              aria-pressed={activeTemperaturePreset === preset.id}
              className={activeTemperaturePreset === preset.id ? 'active' : ''}
              key={preset.id}
              type="button"
              onClick={() => onChange({ ...stage, model_settings: { ...stage.model_settings, temperature: preset.value } })}
            >
              {preset.label}<small>{preset.value.toFixed(1)}</small>
            </button>
          ))}
        </div>
        <details className="stage-temperature-custom">
          <summary>自定义数值</summary>
          <label>
            温度 0.0-1.4
            <input
              max="1.4"
              min="0"
              step="0.05"
              type="number"
              value={stage.model_settings.temperature}
              onChange={(event) => onChange({
                ...stage,
                model_settings: { ...stage.model_settings, temperature: clampTemperature(Number(event.target.value)) },
              })}
            />
          </label>
        </details>
      </div>
      {imageQuality ? (
        <label className="stage-image-quality">
          封面输出质量
          <select
            value={String(imageQuality.default ?? 'medium')}
            onChange={(event) => onChange(updateField(stage, 'image_quality', event.target.value))}
          >
            {(imageQuality.options ?? []).map((option) => <option key={option} value={option}>{imageQualityLabel(option)}</option>)}
          </select>
        </label>
      ) : null}
      <div className="stage-budget-readonly" data-readonly="true">
        <span>单次生成上限</span>
        <strong>{(stage.generation_budget?.max_tokens ?? stage.model_settings.max_tokens).toLocaleString()} tokens</strong>
        <small>跟随本阶段生成预算，不单独修改</small>
      </div>
    </section>
  );
}

function updateField(stage: WorkflowStage, key: string, value: unknown): WorkflowStage {
  return {
    ...stage,
    input_schema: stage.input_schema.map((field) => (field.key === key ? { ...field, default: value } : field)),
  };
}

function imageQualityLabel(value: string) {
  if (value === 'low') return '草稿';
  if (value === 'high') return '精细';
  return '标准';
}
