import * as Switch from '@radix-ui/react-switch';
import { CheckCircle2, ChevronDown, ListRestart, Settings2, Trash2 } from 'lucide-react';
import type { ProviderProfile, WorkflowDefinition } from '../contracts';
import { LoadingButton } from '../layout/LoadingButton';
import { providerKindForUi, providerNameForUi } from '../lib/display';
import { ModelOptionInput } from './fields/ModelOptionInput';
import { ProviderTemplateSelect } from './ProviderTemplateSelect';
import { providerDeletionBlockReason } from './settingsWorkflow';
import { providerSecretStatus, type ProviderAvailabilityState } from './useProviderAvailability';
import type { ProviderOperations } from './useProviderOperations';

type Props = {
  availability: ProviderAvailabilityState;
  operations: ProviderOperations;
  pendingDelete: boolean;
  provider: ProviderProfile;
  workflow: WorkflowDefinition;
  onAddModelOption: (providerId: string, model: string) => void;
  onCancelDelete: () => void;
  onChange: (provider: ProviderProfile) => void;
  onRequestDelete: () => void;
};

export function ProviderEditor({
  availability,
  operations,
  pendingDelete,
  provider,
  workflow,
  onAddModelOption,
  onCancelDelete,
  onChange,
  onRequestDelete,
}: Props) {
  const busy = operations.providerBusy(provider.id);
  const deletionBlock = providerDeletionBlockReason(workflow, provider.id);
  const status = operations.statuses[provider.id];
  return (
    <article aria-busy={busy} className="provider-editor">
      <div className="provider-editor-head">
        <strong>{providerNameForUi(provider)}</strong>
        <div className="provider-editor-tools">
          <span className="switch-line">
            <Switch.Root
              aria-label={`启用 ${providerNameForUi(provider)}`}
              className="switch-root"
              checked={provider.enabled}
              disabled={busy}
              onCheckedChange={(enabled) => onChange({ ...provider, enabled })}
            >
              <Switch.Thumb className="switch-thumb" />
            </Switch.Root>
            启用
          </span>
          <button
            aria-label={`删除接口 ${providerNameForUi(provider)}`}
            className="provider-delete-trigger"
            disabled={busy || Boolean(deletionBlock)}
            title={deletionBlock || '删除未被引用的接口'}
            type="button"
            onClick={onRequestDelete}
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      <div className="provider-editor-summary">
        <span>{providerKindForUi(provider.kind)}</span>
        <span>{provider.default_model || '模型未设置'}</span>
        <span>{providerSecretStatus(provider, availability)}</span>
      </div>
      <details className="provider-editor-disclosure" open={pendingDelete || undefined}>
        <summary><span>配置与检查</span><ChevronDown aria-hidden size={15} /></summary>
        {pendingDelete ? (
          <div className="provider-delete-confirm" role="alert">
            <span>删除后将同时清除该服务保存在本机的 API Key。此操作不会触发模型请求。</span>
            <div>
              <button disabled={busy} type="button" onClick={onCancelDelete}>取消</button>
              <LoadingButton className="provider-delete-action" loading={status?.type === 'deleting'} loadingLabel="正在删除" onClick={() => operations.deleteProvider(provider)}>
                <Trash2 size={14} />确认删除
              </LoadingButton>
            </div>
          </div>
        ) : null}
        <form className="provider-primary-flow" onSubmit={(event) => {
          event.preventDefault();
          operations.saveAndTestProvider(provider);
        }}>
          <ProviderTemplateSelect busy={busy} provider={provider} templates={availability.templates} onChange={onChange} />
          <label>
            API Key
            <input
              autoComplete="off"
              disabled={busy}
              placeholder="仅发送到本机服务，浏览器不保存明文"
              type="password"
              value={operations.secretInputs[provider.id] ?? ''}
              onChange={(event) => operations.setSecretInput(provider.id, event.target.value)}
            />
          </label>
          {operations.secretInputs[provider.id]?.trim() ? <span className="unsaved-draft-status" role="status">密钥尚未保存</span> : null}
          <ModelOptionInput
            label="默认模型"
            disabled={busy}
            providerId={provider.id}
            providers={workflow.provider_profiles}
            value={provider.default_model}
            onAddOption={onAddModelOption}
            onChange={(model: string) => onChange({ ...provider, default_model: model })}
          />
          <div className="provider-primary-status">
            <span>{providerSecretStatus(provider, availability)} · 密钥仅保存在本机服务</span>
            <LoadingButton className="provider-primary-action" disabled={busy} loading={status?.type === 'saving' || status?.type === 'testing'} loadingLabel={status?.type === 'testing' ? '正在检查' : '正在保存'} type="submit">
              <CheckCircle2 size={14} />保存并检查
            </LoadingButton>
          </div>
          {status?.message ? (
            <div aria-atomic="true" aria-live="polite" className={`provider-status ${status.type}`} role={status.type === 'error' ? 'alert' : 'status'}>{status.message}</div>
          ) : null}
        </form>
        <details className="provider-advanced-fields">
          <summary><Settings2 aria-hidden size={14} />高级连接信息<ChevronDown aria-hidden size={14} /></summary>
          <div className="settings-grid provider-connection-grid">
            <label>名称<input disabled={busy} value={providerNameForUi(provider)} onChange={(event) => onChange({ ...provider, name: event.target.value })} /></label>
            <label>Base URL<input disabled={busy} value={provider.base_url} onChange={(event) => onChange({ ...provider, base_url: event.target.value })} placeholder="https://api.example.com/v1" /></label>
            {provider.kind === 'openai-compatible-image' ? (
              <label>单张预计费用（USD）<input disabled={busy} min="0" step="0.001" type="number" value={provider.estimated_cost_per_output_usd ?? ''} onChange={(event) => onChange({ ...provider, estimated_cost_per_output_usd: event.target.value ? Number(event.target.value) : null })} /></label>
            ) : null}
          </div>
          <LoadingButton
            className="provider-sync-models"
            disabled={busy}
            loading={status?.type === 'discovering'}
            loadingLabel="同步中"
            title="读取模型目录，不触发文本或图片生成"
            onClick={() => operations.discoverModels(provider)}
          >
            <ListRestart size={14} />同步模型目录
          </LoadingButton>
        </details>
      </details>
    </article>
  );
}
