import '../../../styles/entry-settings.css';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, SlidersHorizontal, X } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import type { KnowledgeDocument, SettingsSectionSummary, WorkflowDefinition } from '../contracts';
import { DangerConfirmationDialog } from '../layout/DangerConfirmationDialog';
import { buildSettingsSections } from '../lib/setupProgress';
import { useDialogExitPresence } from '../state/useDialogExitPresence';
import type { SaveStatus } from '../state/useWorkflowAutosave';
import { CreationModeSetupSection } from '../planning/CreationModeSetupSection';
import { ProviderManagerSheet } from './ProviderManagerSheet';
import { useProviderReadinessContext } from './ProviderReadinessContext';
import { SettingsOverview } from './SettingsOverview';
import { withoutStageProviderExceptions } from './settingsWorkflow';

type Props = {
  open: boolean;
  apiWarning?: string;
  knowledgeDocuments: KnowledgeDocument[];
  saveStatus: SaveStatus;
  workflow: WorkflowDefinition;
  onOpenChange: (open: boolean) => void;
  onOpenKnowledgeManager: () => void;
  onQualityModeChange: (mode: WorkflowDefinition['quality_mode']) => void;
  onSelectStage: (stageId: string) => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export function SettingsDialog({
  apiWarning,
  knowledgeDocuments,
  onOpenChange,
  onOpenKnowledgeManager,
  onQualityModeChange,
  onSelectStage,
  onWorkflowChange,
  open,
  saveStatus,
  workflow,
}: Props) {
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [activeEditorId, setActiveEditorId] = useState<'creation-mode' | null>(null);
  const [providerManagerOpen, setProviderManagerOpen] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const readiness = useProviderReadinessContext();
  const { exiting, presentOpen } = useDialogExitPresence(open);
  const sections = useMemo(() => {
    const derived = buildSettingsSections({
      knowledgeDocuments,
      readiness: readiness.status === 'ready' ? readiness.report : undefined,
      workflow,
    });
    return derived;
  }, [knowledgeDocuments, readiness.report, readiness.status, saveStatus, workflow]);

  const handleSection = (section: SettingsSectionSummary) => {
    if (section.id === 'ai-service') {
      setProviderManagerOpen(true);
      return;
    }
    if (section.id === 'creation-mode') {
      setActiveEditorId((current) => current === 'creation-mode' ? null : 'creation-mode');
      return;
    }
    if (section.id === 'references') {
      onOpenChange(false);
      onSelectStage('info');
      onOpenKnowledgeManager();
      return;
    }
    if (section.action?.target) {
      onOpenChange(false);
      onSelectStage(section.action.target);
    }
  };

  return (
    <>
      <Dialog.Root open={presentOpen} onOpenChange={onOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="settings-overlay app-overlay-backdrop app-radix-backdrop" data-exiting={exiting || undefined} />
          <Dialog.Content
            asChild
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
            <section className="settings-dialog settings-overview-dialog app-radix-dialog-presence" data-exiting={exiting || undefined}>
              <div className="settings-dialog-inner app-dialog-surface">
                <div className="settings-head">
                  <div>
                    <p className="eyebrow">项目设置</p>
                    <Dialog.Title>创作准备总览</Dialog.Title>
                    <Dialog.Description>每项配置只有一个主编辑位置。这里汇总当前状态，并把你带到真正会写回的位置。</Dialog.Description>
                  </div>
                  <Dialog.Close aria-label="关闭项目设置" className="modal-close settings-close"><X size={22} /></Dialog.Close>
                </div>
                {apiWarning ? <div className="settings-warning app-error-state" role="alert"><AlertTriangle size={16} /><span>{apiWarning}</span></div> : null}
                {saveStatus === 'failed' ? <div className="settings-warning app-error-state" role="alert"><AlertTriangle size={16} /><span>自动保存失败，当前浏览器草稿仍保留；请恢复连接后重试。</span></div> : null}
                <SettingsOverview
                  activeEditorId={activeEditorId}
                  sections={sections}
                  onEditRequest={handleSection}
                  onResetStageExceptions={() => setResetConfirmOpen(true)}
                >
                  {activeEditorId === 'creation-mode' ? (
                    <div className="settings-mode-editor">
                      <div className="settings-inline-editor-head"><span><SlidersHorizontal size={15} />修改创作模式</span><button type="button" onClick={() => setActiveEditorId(null)}>完成</button></div>
                      <CreationModeSetupSection context="settings" value={workflow.quality_mode} onChange={onQualityModeChange} />
                    </div>
                  ) : null}
                </SettingsOverview>
              </div>
            </section>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <ProviderManagerSheet
        open={providerManagerOpen}
        workflow={workflow}
        onOpenChange={setProviderManagerOpen}
        onReadinessRefresh={readiness.refresh}
        onWorkflowChange={onWorkflowChange}
      />
      <DangerConfirmationDialog
        confirmLabel="恢复默认"
        description="所有阶段将重新继承默认文本和封面服务；全局备用链保持不变。故事内容和阶段产物不会改变。"
        details={['创作发散度、质量方式和产物字段保持不变。', '工作流会按现有自动保存机制写入。']}
        modeClass={`mode-${workflow.quality_mode}`}
        open={resetConfirmOpen}
        title="恢复全部阶段例外？"
        onCancel={() => setResetConfirmOpen(false)}
        onConfirm={() => {
          onWorkflowChange(withoutStageProviderExceptions(workflow));
          setResetConfirmOpen(false);
        }}
      />
    </>
  );
}
