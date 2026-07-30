import { ArrowDown, ArrowUp, Plus, ShieldCheck, Trash2 } from 'lucide-react';
import type { ProviderProfile, WorkflowDefinition } from '../contracts';
import { modelNameForUi, providerNameForUi } from '../lib/display';
import { OptionField } from './fields/OptionField';
import {
  globalFallbackTargets,
  type GlobalFallbackChannel,
  withGlobalFallbackProviders,
} from './settingsWorkflow';

type Props = {
  workflow: WorkflowDefinition;
  onChange: (workflow: WorkflowDefinition) => void;
};

export function GlobalFallbackChainEditor({ workflow, onChange }: Props) {
  return (
    <section aria-labelledby="global-fallback-title" className="global-fallback-editor">
      <div className="global-fallback-heading">
        <span><ShieldCheck aria-hidden size={15} /><strong id="global-fallback-title">全局备用链</strong></span>
        <small>主服务不可用时按顺序切换；所有阶段共用</small>
      </div>
      <FallbackChannel workflow={workflow} channel="text" label="文本生成备用" onChange={onChange} />
      <FallbackChannel workflow={workflow} channel="image" label="封面生成备用" onChange={onChange} />
    </section>
  );
}

function FallbackChannel({
  channel,
  label,
  workflow,
  onChange,
}: Props & { channel: GlobalFallbackChannel; label: string }) {
  const kind: ProviderProfile['kind'] = channel === 'image' ? 'openai-compatible-image' : 'openai-compatible';
  const providers = workflow.provider_profiles.filter((provider) => provider.enabled && provider.kind === kind);
  const primary = providers.find((provider) => provider.is_global_default) ?? providers[0];
  const targets = globalFallbackTargets(workflow, channel);
  const ids = targets.map((target) => target.provider_profile_id);
  const available = providers.filter((provider) => provider.id !== primary?.id);
  const canAdd = ids.length < 3 && available.some((provider) => !ids.includes(provider.id));

  const commit = (nextIds: string[]) => onChange(withGlobalFallbackProviders(workflow, channel, nextIds));

  return (
    <div className="global-fallback-channel">
      <div className="global-fallback-channel-head">
        <span><strong>{label}</strong><small>主服务：{primary ? providerNameForUi(primary) : '未设置'}</small></span>
        <button
          aria-label={`添加${label}`}
          className="icon-button"
          disabled={!canAdd}
          title={`添加${label}`}
          type="button"
          onClick={() => {
            const provider = available.find((item) => !ids.includes(item.id));
            if (provider) commit([...ids, provider.id]);
          }}
        ><Plus size={14} /></button>
      </div>
      {targets.length ? targets.map((target, index) => {
        const provider = providers.find((item) => item.id === target.provider_profile_id);
        const selectable = available.filter((item) => item.id === target.provider_profile_id || !ids.includes(item.id));
        return (
          <div className="global-fallback-row" key={`${channel}-${target.provider_profile_id}`}>
            <span className="global-fallback-priority">{index + 1}</span>
            <OptionField
              label={`${label} ${index + 1}`}
              options={selectable.map((item) => ({ value: item.id, label: providerNameForUi(item), meta: modelNameForUi(item.default_model) }))}
              value={target.provider_profile_id}
              onValueChange={(providerId) => commit(ids.map((id, itemIndex) => itemIndex === index ? providerId : id))}
            />
            <small>{modelNameForUi(provider?.default_model ?? target.model)}</small>
            <div className="global-fallback-actions">
              <button aria-label="提高备用优先级" className="icon-button" disabled={index === 0} type="button" onClick={() => commit(move(ids, index, -1))}><ArrowUp size={13} /></button>
              <button aria-label="降低备用优先级" className="icon-button" disabled={index === ids.length - 1} type="button" onClick={() => commit(move(ids, index, 1))}><ArrowDown size={13} /></button>
              <button aria-label="移除备用服务" className="icon-button danger" type="button" onClick={() => commit(ids.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={13} /></button>
            </div>
          </div>
        );
      }) : <p className="global-fallback-empty">未设置备用服务；主服务失败时暂停并保留恢复点。</p>}
    </div>
  );
}

function move(items: string[], index: number, direction: -1 | 1) {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= items.length) return items;
  const next = [...items];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}
