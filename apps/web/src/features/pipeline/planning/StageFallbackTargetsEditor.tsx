import { ChevronDown, ChevronUp, Plus, ShieldCheck, Trash2 } from 'lucide-react';
import type { ProviderProfile, WorkflowStage } from '../contracts';
import {
  addFallbackTarget,
  fallbackTargets,
  moveFallbackTarget,
  removeFallbackTarget,
  type FallbackChannel,
  updateFallbackTarget,
} from '../lib/providerFallback';
import { ModelOptionInput } from '../settings/fields/ModelOptionInput';
import { OptionField } from '../settings/fields/OptionField';
import { providerOptionItems } from '../settings/providerOptionItems';

type Props = {
  stage: WorkflowStage;
  providers: ProviderProfile[];
  onAddModelOption: (providerId: string, model: string) => void;
  onChange: (stage: WorkflowStage) => void;
};

export function StageFallbackTargetsEditor(props: Props) {
  const textCount = fallbackTargets(props.stage, 'text').length;
  const imageCount = fallbackTargets(props.stage, 'image').length;
  return (
    <details className="fallback-targets-editor">
      <summary>
        <span><ShieldCheck size={15} />故障转移</span>
        <small>{textCount + imageCount ? `${textCount + imageCount} 个备用` : '未启用'}</small>
      </summary>
      <FallbackChannelEditor {...props} channel="text" label={props.stage.type === 'cover_image' ? '封面规划备用' : '文本生成备用'} />
      {props.stage.type === 'cover_image' ? <FallbackChannelEditor {...props} channel="image" label="图片生成备用" /> : null}
    </details>
  );
}

function FallbackChannelEditor({ stage, providers, onAddModelOption, onChange, channel, label }: Props & { channel: FallbackChannel; label: string }) {
  const targets = fallbackTargets(stage, channel);
  const kind = channel === 'image' ? 'openai-compatible-image' : 'openai-compatible';
  const primaryId = channel === 'image' ? stage.image_provider_profile_id : stage.provider_profile_id;
  const available = providers.filter((provider) => provider.enabled && provider.kind === kind && provider.id !== primaryId);
  const used = new Set(targets.map((target) => target.provider_profile_id));
  const canAdd = targets.length < 3 && available.some((provider) => !used.has(provider.id));
  return (
    <div className="fallback-channel-editor">
      <div className="fallback-channel-heading">
        <strong>{label}</strong>
        <button type="button" className="icon-button" title={`添加${label}`} disabled={!canAdd} onClick={() => onChange(addFallbackTarget(stage, providers, channel))}>
          <Plus size={15} />
        </button>
      </div>
      {targets.map((target, index) => {
        const selectable = available.filter((provider) => provider.id === target.provider_profile_id || !used.has(provider.id));
        return (
          <div className="fallback-target-row" key={`${channel}-${target.priority}-${target.provider_profile_id}`}>
            <div className="fallback-priority-actions" aria-label={`备用优先级 ${target.priority}`}>
              <span>{target.priority}</span>
              <button type="button" className="icon-button" title="上移" disabled={index === 0} onClick={() => onChange(moveFallbackTarget(stage, channel, target.priority, -1))}><ChevronUp size={14} /></button>
              <button type="button" className="icon-button" title="下移" disabled={index === targets.length - 1} onClick={() => onChange(moveFallbackTarget(stage, channel, target.priority, 1))}><ChevronDown size={14} /></button>
            </div>
            <OptionField
              className="fallback-provider-field"
              label="备用服务"
              options={providerOptionItems(selectable)}
              value={target.provider_profile_id}
              onValueChange={(providerId) => onChange(updateFallbackTarget(stage, providers, channel, target.priority, { provider_profile_id: providerId }))}
            />
            <ModelOptionInput
              label="备用模型"
              providerId={target.provider_profile_id}
              providers={providers}
              value={target.model}
              onAddOption={onAddModelOption}
              onChange={(model) => onChange(updateFallbackTarget(stage, providers, channel, target.priority, { model }))}
            />
            <label className="fallback-enabled-toggle">
              <input type="checkbox" checked={target.enabled} onChange={(event) => onChange(updateFallbackTarget(stage, providers, channel, target.priority, { enabled: event.target.checked }))} />
              启用
            </label>
            <button type="button" className="icon-button danger" title="移除备用" onClick={() => onChange(removeFallbackTarget(stage, channel, target.priority))}><Trash2 size={15} /></button>
          </div>
        );
      })}
    </div>
  );
}
