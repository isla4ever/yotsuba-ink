import '../../../styles/entry-settings.css';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, CheckCircle2, KeyRound, PlusCircle, X } from 'lucide-react';
import { useRef, useState } from 'react';
import type { ProviderProfile, WorkflowDefinition } from '../contracts';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { useDialogExitPresence } from '../state/useDialogExitPresence';
import { useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
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
  open: boolean;
  workflow: WorkflowDefinition;
  onOpenChange: (open: boolean) => void;
  onReadinessRefresh: () => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export function ProviderManagerSheet({ open, workflow, onOpenChange, onReadinessRefresh, onWorkflowChange }: Props) {
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [pendingDeleteProviderId, setPendingDeleteProviderId] = useState('');
  const availability = useProviderAvailability(open);
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
  const dirty = Object.values(operations.secretInputs).some((value) => Boolean(value.trim()));
  const guard = useUnsavedDraftGuard({ dirty, scopeLabel: 'API Key 草稿' });
  const { exiting, presentOpen } = useDialogExitPresence(open);

  const requestClose = () => {
    guard.requestAction({ kind: 'close', scopeLabel: 'API Key 草稿' }, () => {
      onOpenChange(false);
      onReadinessRefresh();
    });
  };

  return (
    <Dialog.Root open={presentOpen} onOpenChange={(nextOpen) => nextOpen ? onOpenChange(true) : requestClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="provider-manager-overlay app-overlay-backdrop app-radix-backdrop" data-exiting={exiting || undefined} />
        <Dialog.Content
          asChild
          onEscapeKeyDown={(event) => {
            const target = event.target;
            if (target instanceof HTMLElement && target.closest('.option-field-positioner, .option-field-popup, .option-field-search-input')) {
              event.preventDefault();
            }
          }}
          onFocusOutside={(event) => {
            const target = event.target;
            if (target instanceof HTMLElement && target.closest('.option-field-positioner, .option-field-popup, .option-field-backdrop')) {
              event.preventDefault();
            }
          }}
          onInteractOutside={(event) => {
            const target = event.target;
            if (target instanceof HTMLElement && target.closest('.option-field-positioner, .option-field-popup, .option-field-backdrop')) {
              event.preventDefault();
            }
          }}
          onOpenAutoFocus={() => {
            const target = document.activeElement;
            returnFocusRef.current = target instanceof HTMLElement ? target : null;
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            const target = returnFocusRef.current;
            window.setTimeout(() => {
              if (target?.isConnected) target.focus();
            }, 0);
          }}
        >
          <section className="provider-manager-sheet app-radix-dialog-presence" data-exiting={exiting || undefined}>
            <header className="provider-manager-head">
              <div>
                <p className="eyebrow">AI 服务</p>
                <Dialog.Title>连接服务与默认模型</Dialog.Title>
                <Dialog.Description>连接信息只配置一次。未设置阶段例外时，所有创作阶段继承这里的默认服务。</Dialog.Description>
              </div>
              <Dialog.Close aria-label="关闭 AI 服务管理" className="modal-close"><X size={20} /></Dialog.Close>
            </header>

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

            <footer className="provider-manager-foot">
              <span><CheckCircle2 size={14} />密钥只发送到本机服务，前端不保存明文。</span>
              <button className="tech-button provider-manager-complete" type="button" onClick={requestClose}>完成</button>
            </footer>
            {guard.intent ? (
              <UnsavedDraftDialog
                inline
                intent={guard.intent}
                modeClass={`mode-${workflow.quality_mode}`}
                onCancel={guard.cancelDiscard}
                onDiscard={() => {
                  operations.clearSecretInputs();
                  guard.confirmDiscard();
                }}
              />
            ) : null}
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
