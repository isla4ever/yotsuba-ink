import { BadgeCheck, RotateCcw } from 'lucide-react';
import type { ProviderProfile, QualityMode, WorkflowStage } from '../contracts';
import { modelNameForUi } from '../lib/display';
import {
  clampTemperature,
  coverImageQuality,
  temperaturePresetFor,
  temperaturePresets,
} from '../lib/stageConfigurationPolicy';
import { removePrimaryFromFallbacks } from '../lib/providerFallback';
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
        label={stage.type === 'cover_image' ? '封面规划文本服务' : '文本生成服务'}
        options={providerOptionItems(textProviders)}
        value={stage.provider_profile_id}
        onValueChange={(providerId) => {
          const provider = textProviders.find((item) => item.id === providerId);
          const nextModel = provider?.default_model ?? stage.model_settings.model;
          onChange(removePrimaryFromFallbacks({
            ...stage,
            provider_profile_id: providerId,
            model_settings: { ...stage.model_settings, model: nextModel },
            variant_policy: stage.variant_policy.judge_provider_profile_id === 'inherit'
              ? { ...stage.variant_policy, judge_model: nextModel }
              : stage.variant_policy,
          }, 'text', providerId));
        }}
      />
      {stage.type === 'cover_image' ? (
        <OptionField
          label="封面生成服务"
          options={providerOptionItems(imageProviders)}
          status={imageProvider ? 'ready' : 'warning'}
          statusText={imageProvider ? `图片模型 ${modelNameForUi(imageProvider.default_model)}` : '尚未连接图片服务'}
          value={stage.image_provider_profile_id ?? ''}
          onValueChange={(providerId) => onChange(removePrimaryFromFallbacks({ ...stage, image_provider_profile_id: providerId }, 'image', providerId))}
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
          variant_policy: stage.variant_policy.judge_provider_profile_id === 'inherit'
            ? { ...stage.variant_policy, judge_model: model }
            : stage.variant_policy,
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

export function StageVariantCompareSection({
  mode,
  stage,
  onChange,
}: {
  mode: QualityMode;
  stage: WorkflowStage;
  onChange: (stage: WorkflowStage) => void;
}) {
  if (stage.type !== 'chapter_text' || mode !== 'balanced') return null;
  const enabled = Boolean(getField(stage, 'enable_version_compare')?.default);
  const count = Math.max(2, Math.min(3, Number(getField(stage, 'version_candidate_count')?.default ?? 2)));

  return (
    <section className="config-section version-compare-section">
      <div className="version-compare-head">
        <span><strong>多版本比对</strong><small>正文可主动生成多个候选并评审，用量按候选数增加</small></span>
        <label className="inline-switch">
          <input checked={enabled} type="checkbox" onChange={(event) => onChange(updateVersionCompare(stage, event.target.checked, count))} />
          <span>{enabled ? '已开启' : '已关闭'}</span>
        </label>
      </div>
      {enabled ? (
        <div className="version-count-control">
          <span>候选数</span>
          <div role="group" aria-label="候选版本数">
            {[2, 3].map((value) => (
              <button aria-pressed={count === value} key={value} type="button" onClick={() => onChange(updateVersionCompare(stage, true, value))}>{value} 版</button>
            ))}
          </div>
          <small>评审继承正文服务与模型：{modelNameForUi(stage.model_settings.model)}</small>
        </div>
      ) : null}
    </section>
  );
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

function updateVersionCompare(stage: WorkflowStage, enabled: boolean, count: number) {
  const next = updateField(updateField(stage, 'enable_version_compare', enabled), 'version_candidate_count', count);
  return {
    ...next,
    variant_policy: { ...next.variant_policy, enabled, candidate_count: enabled ? count : 1, retry_on_fail: enabled },
  };
}

function imageQualityLabel(value: string) {
  if (value === 'low') return '草稿';
  if (value === 'high') return '精细';
  return '标准';
}
