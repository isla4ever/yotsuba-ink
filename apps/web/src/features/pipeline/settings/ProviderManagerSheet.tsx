import '../../../styles/entry-settings.css';
import * as Dialog from '@radix-ui/react-dialog';
import { CheckCircle2, X } from 'lucide-react';
import { useRef, useState } from 'react';
import type { WorkflowDefinition } from '../contracts';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { useDialogExitPresence } from '../state/useDialogExitPresence';
import { useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { ProviderManagerPanel, type ProviderManagerPanelHandle } from './ProviderManagerPanel';

type Props = {
  open: boolean;
  workflow: WorkflowDefinition;
  onOpenChange: (open: boolean) => void;
  onReadinessRefresh: () => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export function ProviderManagerSheet({ open, workflow, onOpenChange, onReadinessRefresh, onWorkflowChange }: Props) {
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const panelRef = useRef<ProviderManagerPanelHandle | null>(null);
  const [dirty, setDirty] = useState(false);
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

            <ProviderManagerPanel
              active={open}
              ref={panelRef}
              workflow={workflow}
              onDirtyChange={setDirty}
              onReadinessRefresh={onReadinessRefresh}
              onWorkflowChange={onWorkflowChange}
            />

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
                  panelRef.current?.clearSecretInputs();
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
