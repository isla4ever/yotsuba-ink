import { AlertTriangle, KeyRound, PlusCircle } from 'lucide-react';
import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import type { ProviderProfile, WorkflowDefinition } from '../contracts';
import { ProviderCreateControl } from './ProviderCreateControl';
import { ProviderEditor } from './ProviderEditor';
import { OptionField } from './fields/OptionField';
import { providerOptionItems } from './providerOptionItems';
import {
  replaceProviderProfile,
  withProviderModelOption,
  withProviderProfile,
  withoutProviderProfile,
} from './settingsWorkflow';
import { useProviderAvailability } from './useProviderAvailability';
import { useProviderOperations } from './useProviderOperations';

type Props = {
  active: boolean;
  workflow: WorkflowDefinition;
  onDirtyChange?: (dirty: boolean) => void;
  onReadinessRefresh: () => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export type ProviderManagerPanelHandle = {
  clearSecretInputs: () => void;
};

/**
 * Provider management body shared by the settings page (inline) and the
 * guided-setup sheet. The imperative handle exposes API-key draft state so
 * dialog hosts can guard close against unsaved secrets.
 */
export const ProviderManagerPanel = forwardRef<ProviderManagerPanelHandle, Props>(function ProviderManagerPanel(
  { active, workflow, onDirtyChange, onReadinessRefresh, onWorkflowChange },
  ref,
) {
  const [pendingDeleteProviderId, setPendingDeleteProviderId] = useState('');
  const availability = useProviderAvailability(active);
  const textProviders = workflow.provider_profiles.filter((provider) => provider.kind === 'openai-compatible');
  const imageProviders = workflow.provider_profiles.filter((provider) => provider.kind === 'openai-compatible-image');
  const globalText = textProviders.find((provider) => provider.is_global_default) ?? textProviders[0];
  const globalImage = imageProviders.find((provider) => provider.is_global_default) ?? imageProviders[0];

  const updateProvider = (provider: ProviderProfile) => {
    onWorkflowChange(replaceProviderProfile(workflow, provider));
  };
  const operations = useProviderOperations({
    onOperationSucceeded: onReadinessRefresh,
    onProviderCreated: (provider) => onWorkflowChange(withProviderProfile(workflow, provider)),
    onProviderDeleted: (providerId) => {
      setPendingDeleteProviderId('');
      onWorkflowChange(withoutProviderProfile(workflow, providerId));
    },
    onProvidersUpdated: (providers) => onWorkflowChange({ ...workflow, provider_profiles: providers }),
    onProviderUpdated: updateProvider,
  });

  useImperativeHandle(ref, () => ({
    clearSecretInputs: operations.clearSecretInputs,
  }), [operations.clearSecretInputs]);

  const dirty = Object.values(operations.secretInputs).some((value) => Boolean(value.trim()));
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  return (
    <div className="provider-manager-body">
      {availability.status === 'failed' ? (
        <div className="settings-warning provider-manager-notice app-error-state" role="alert"><AlertTriangle size={15} />服务列表暂时无法同步，当前草稿仍保留。</div>
      ) : null}

      <div className="provider-default-strip">
        <OptionField
          label="文本生成服务"
          options={providerOptionItems(textProviders)}
          status={globalText ? 'ready' : 'warning'}
          statusText={globalText ? `默认生成模型：${globalText.default_model}` : '尚未配置文本生成服务'}
          value={globalText?.id ?? ''}
          onValueChange={(providerId) => {
            const provider = textProviders.find((item) => item.id === providerId);
            if (provider) operations.setGlobalDefault(provider);
          }}
        />
        <OptionField
          label="封面生成服务"
          options={providerOptionItems(imageProviders)}
          status={globalImage ? 'ready' : 'warning'}
          statusText={globalImage ? `默认封面模型：${globalImage.default_model}` : '尚未配置封面生成服务'}
          value={globalImage?.id ?? ''}
          onValueChange={(providerId) => {
            const provider = imageProviders.find((item) => item.id === providerId);
            if (provider) operations.setGlobalDefault(provider);
          }}
        />
      </div>

      <div className="provider-manager-create">
        <span><KeyRound size={15} />新增服务</span>
        <ProviderCreateControl
          existingIds={workflow.provider_profiles.map((provider) => provider.id)}
          templates={availability.templates}
          onCreate={operations.createProvider}
        />
      </div>

      <div className="provider-manager-list">
        {workflow.provider_profiles.length ? workflow.provider_profiles.map((provider) => (
          <ProviderEditor
            availability={availability}
            key={provider.id}
            operations={operations}
            pendingDelete={pendingDeleteProviderId === provider.id}
            provider={provider}
            workflow={workflow}
            onAddModelOption={(providerId, model) => onWorkflowChange(withProviderModelOption(workflow, providerId, model))}
            onCancelDelete={() => setPendingDeleteProviderId('')}
            onChange={updateProvider}
            onRequestDelete={() => setPendingDeleteProviderId(provider.id)}
          />
        )) : (
          <div className="provider-empty-state" role="status">
            <PlusCircle aria-hidden size={19} />
            <span><strong>还没有 AI 服务</strong><small>从上方选择厂商模板并添加接口，文本与封面服务可以分别配置。</small></span>
          </div>
        )}
      </div>
    </div>
  );
});
