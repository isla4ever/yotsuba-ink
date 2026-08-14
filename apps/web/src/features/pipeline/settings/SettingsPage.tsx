import '../../../styles/entry-settings.css';
import { AlertTriangle, CheckCircle2, KeyRound, RefreshCw, Settings, SlidersHorizontal } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { KnowledgeDocument, SettingsSectionSummary, WorkflowDefinition } from '../contracts';
import { DangerConfirmationDialog } from '../layout/DangerConfirmationDialog';
import { LoadingButton } from '../layout/LoadingButton';
import { buildSettingsSections, providerReadinessSummary } from '../lib/setupProgress';
import { qualityModeProfiles } from '../lib/qualityModes';
import type { SaveStatus } from '../state/useWorkflowAutosave';
import { CreationModeSetupSection } from '../planning/CreationModeSetupSection';
import { ProviderManagerPanel } from './ProviderManagerPanel';
import { useProviderReadinessContext } from './ProviderReadinessContext';
import { SettingsOverview } from './SettingsOverview';
import { withoutStageProviderExceptions } from './settingsWorkflow';

type Props = {
  apiWarning?: string;
  knowledgeDocuments: KnowledgeDocument[];
  saveStatus: SaveStatus;
  /**
   * 'project': the per-book settings page (readiness overview + creation mode
   * + provider bindings). 'global': the studio-scoped page — only the AI
   * service pool that every book inherits; book-specific sections are hidden.
   */
  scope?: 'project' | 'global';
  workflow: WorkflowDefinition;
  onOpenKnowledgeManager: () => void;
  onQualityModeChange: (mode: WorkflowDefinition['quality_mode']) => void;
  onSelectStage: (stageId: string) => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

/**
 * Full-page settings surface (was a portal dialog). Sections keep the single
 * source-of-truth rule: the overview summarizes state and links to the one
 * place each config actually writes back; provider management is inline.
 */
export function SettingsPage({
  apiWarning,
  knowledgeDocuments,
  onOpenKnowledgeManager,
  onQualityModeChange,
  onSelectStage,
  onWorkflowChange,
  saveStatus,
  scope = 'project',
  workflow,
}: Props) {
  const globalScope = scope === 'global';
  const [activeEditorId, setActiveEditorId] = useState<'creation-mode' | null>(null);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const readiness = useProviderReadinessContext();
  const sections = useMemo(() => buildSettingsSections({
    knowledgeDocuments,
    readiness: readiness.status === 'ready' ? readiness.report : undefined,
    workflow,
  }), [knowledgeDocuments, readiness.report, readiness.status, workflow]);

  const readinessLabel = readiness.status === 'loading'
    ? '正在检查配置'
    : readiness.status === 'failed'
      ? 'AI 服务检查失败'
      : readiness.report
        ? providerReadinessSummary(readiness.report)
        : 'AI 服务状态尚未确认';

  const handleSection = (section: SettingsSectionSummary) => {
    if (section.id === 'ai-service') {
      document.getElementById('settings-provider-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (section.id === 'creation-mode') {
      setActiveEditorId((current) => current === 'creation-mode' ? null : 'creation-mode');
      return;
    }
    if (section.id === 'references') {
      onOpenKnowledgeManager();
      return;
    }
    if (section.action?.target) {
      onSelectStage(section.action.target);
    }
  };

  return (
    <section aria-labelledby="settings-page-title" className="settings-page workspace-page">
      <header className="workspace-page-head">
        <div className="workspace-page-title">
          <p className="eyebrow">{globalScope ? '工作室 · 全局视角' : '本书设置'}</p>
          <h1 id="settings-page-title"><Settings size={20} />{globalScope ? '全局模型与服务' : '模型与设置'}</h1>
          <span>{globalScope
            ? '这里管理所有作品共享的 AI 服务连接与默认模型；创作模式、阶段例外等书内配置请到对应作品里修改。'
            : '每项配置只有一个主编辑位置。这里汇总当前状态，并把你带到真正会写回的位置。'}</span>
        </div>
        <dl className="workspace-page-stats">
          <div><dt><KeyRound size={13} />AI 服务</dt><dd>{workflow.provider_profiles.length}</dd></div>
          {globalScope ? null : <div><dt><SlidersHorizontal size={13} />创作模式</dt><dd>{modeLabel(workflow.quality_mode)}</dd></div>}
          <div><dt><CheckCircle2 size={13} />自动保存</dt><dd>{saveStatusLabel(saveStatus)}</dd></div>
        </dl>
      </header>

      {apiWarning ? <div className="settings-warning app-error-state" role="alert"><AlertTriangle size={16} /><span>{apiWarning}</span></div> : null}
      {saveStatus === 'failed' ? <div className="settings-warning app-error-state" role="alert"><AlertTriangle size={16} /><span>自动保存失败，当前浏览器草稿仍保留；请恢复连接后重试。</span></div> : null}

      <div className="settings-page-layout nw-reveal-scroll">
        {globalScope ? null : (
        <section aria-labelledby="settings-overview-title" className="settings-page-section">
          <header className="settings-page-section-head">
            <h2 id="settings-overview-title">创作准备总览</h2>
            <span>汇总各项配置的当前状态与主编辑入口。</span>
          </header>
          <SettingsOverview
            activeEditorId={activeEditorId}
            sections={sections}
            onEditRequest={handleSection}
            onResetStageExceptions={() => setResetConfirmOpen(true)}
          >
            {activeEditorId === 'creation-mode' ? (
              <div className="settings-mode-editor nw-reveal">
                <div className="settings-inline-editor-head"><span><SlidersHorizontal size={15} />修改创作模式</span><button type="button" onClick={() => setActiveEditorId(null)}>完成</button></div>
                <CreationModeSetupSection context="settings" value={workflow.quality_mode} onChange={onQualityModeChange} />
              </div>
            ) : null}
          </SettingsOverview>
        </section>
        )}

        <section aria-labelledby="settings-provider-title" className="settings-page-section" id="settings-provider-section">
          <header className="settings-page-section-head">
            <div>
              <h2 id="settings-provider-title">AI 服务与默认模型</h2>
              <span>连接信息只配置一次；未设置阶段例外时，所有创作阶段继承这里的默认服务。</span>
            </div>
            <div className="settings-provider-readiness" data-status={readiness.status}>
              {readiness.status === 'ready' && readiness.report?.ok ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
              <span>{readinessLabel}</span>
              <LoadingButton className="ghost tiny-action" loading={readiness.status === 'loading'} loadingLabel="检查中" onClick={readiness.refresh}>
                <RefreshCw size={13} />重新检查
              </LoadingButton>
            </div>
          </header>
          <ProviderManagerPanel
            active
            workflow={workflow}
            onReadinessRefresh={readiness.refresh}
            onWorkflowChange={onWorkflowChange}
          />
          <p className="settings-provider-note"><CheckCircle2 size={13} />密钥只发送到本机服务，前端不保存明文。</p>
        </section>
      </div>

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
    </section>
  );
}

function modeLabel(mode: WorkflowDefinition['quality_mode']) {
  return qualityModeProfiles[mode].title;
}

function saveStatusLabel(status: SaveStatus) {
  return ({ idle: '就绪', saving: '保存中', saved: '已保存', failed: '保存失败' } as Record<string, string>)[status] ?? status;
}
