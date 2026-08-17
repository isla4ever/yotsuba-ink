import { SlidersHorizontal } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ProjectRecord, QualityMode, WorkflowDefinition } from '../../contracts';
import { LoadingButton } from '../LoadingButton';
import { overlayExitDurationMs } from '../../lib/motion';
import { useOverlayDialog } from '../../state/useOverlayDialog';
import { useDialogExitPresence } from '../../state/useDialogExitPresence';
import {
  initialWizardState,
  defaultTemplateId,
  isOfficialTemplateId,
  templateSummaryLine,
  wizardBack,
  wizardCanSubmit,
  wizardContinue,
  wizardSelectTemplate,
  wizardWithIdea,
  type NewProjectWizardState,
} from './newProjectWizardModel';

type Props = {
  open: boolean;
  initialTemplateId?: string;
  templates: WorkflowDefinition[];
  qualityMode?: QualityMode;
  onClose: () => void;
  onConfigure: (templateId: string) => Promise<void>;
  onCreate: (input: { idea: string; templateId: string }) => Promise<ProjectRecord>;
  onCreated: (project: ProjectRecord) => void;
};

/**
 * New-project wizard: select or configure a pipeline first, then describe the
 * story idea. Brief generates the formal title after project creation.
 */
export function NewProjectWizard({ open, initialTemplateId = '', templates, qualityMode = 'balanced', onClose, onConfigure, onCreate, onCreated }: Props) {
  const freshState = () => initialTemplateId ? wizardSelectTemplate(initialWizardState(), initialTemplateId) : initialWizardState();
  const [state, setState] = useState(freshState);
  const [configuring, setConfiguring] = useState(false);
  const presence = useDialogExitPresence(open);
  const dialogRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.dialog,
    initialFocusSelector: '[role="radio"][aria-checked="true"]',
    onClose,
    open: open && presence.presentOpen,
  });
  const initialDraftMissing = Boolean(
    initialTemplateId
    && !templates.some((template) => template.id === initialTemplateId),
  );
  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === state.templateId) ?? null,
    [state.templateId, templates],
  );

  useEffect(() => {
    if (open) setState(freshState());
    // Reset only when a new wizard entry is requested.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTemplateId, open]);

  if (!presence.presentOpen) return null;

  const close = () => {
    setState(freshState());
    onClose();
  };

  const submit = async (source: NewProjectWizardState) => {
    if (!wizardCanSubmit(source)) return;
    setState({ ...source, submitting: true, error: '' });
    try {
      const project = await onCreate({ idea: source.idea, templateId: source.templateId });
      setState(initialWizardState());
      onCreated(project);
    } catch (error) {
      setState({
        ...source,
        submitting: false,
        error: error instanceof Error ? `创建作品失败：${error.message}` : '创建作品失败。',
      });
    }
  };

  const advance = () => {
    if (state.submitting) return;
    if (state.step === 'idea') {
      void submit(state);
      return;
    }
    setState(wizardContinue(state));
  };

  const primaryLabel = state.step === 'idea' ? '创建并进入立项' : '下一步：填写创作想法';

  const configure = async () => {
    if (!state.templateId || configuring) return;
    setConfiguring(true);
    setState((current) => ({ ...current, error: '' }));
    try {
      await onConfigure(state.templateId);
    } catch (error) {
      setState((current) => ({
        ...current,
        error: error instanceof Error ? `创建本书配置失败：${error.message}` : '创建本书配置失败。',
      }));
      setConfiguring(false);
    }
  };

  const content = (
    <div className={`app-overlay-backdrop studio-wizard-backdrop mode-${qualityMode}${presence.exiting ? ' is-exiting' : ''}`} onClick={(event) => { if (event.currentTarget === event.target) close(); }} role="presentation">
      <section
        aria-label="新建作品"
        aria-modal="true"
        className="app-dialog-surface studio-wizard"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <form onSubmit={(event) => { event.preventDefault(); advance(); }}>
          <p className="eyebrow">{state.step === 'workflow' ? '第 1 步 / 共 2 步' : '第 2 步 / 共 2 步'}</p>
          <h2>{state.step === 'workflow' ? '先确定创作流水线' : '说说你想写的故事'}</h2>
          {state.step === 'workflow' ? (
            <div aria-label="工作流模板" className="studio-wizard-templates" role="radiogroup">
              {initialDraftMissing ? (
                <button aria-checked="true" className="studio-template-option selected" role="radio" type="button">
                  <strong>本书专用创作流水线</strong>
                  <span>已完成一次性配置 · 建书后自动归入作品</span>
                  <em>本次</em>
                </button>
              ) : null}
              {templates.map((template) => (
                <button
                  aria-checked={state.templateId === template.id}
                  className={`studio-template-option${state.templateId === template.id ? ' selected' : ''}`}
                  key={template.id}
                  onClick={() => setState((current) => wizardSelectTemplate(current, template.id))}
                  role="radio"
                  type="button"
                >
                  <strong>{template.name}</strong>
                  <span>{templateSummaryLine(template)}</span>
                  {template.id === defaultTemplateId ? <em>推荐</em> : isOfficialTemplateId(template.id) ? <em>官方</em> : null}
                </button>
              ))}
              {templates.length === 0 && !initialDraftMissing ? <p className="studio-wizard-hint">官方流水线正在载入…</p> : null}
              <button className="studio-wizard-configure" disabled={configuring || !state.templateId} onClick={() => void configure()} type="button">
                <SlidersHorizontal size={14} />
                {configuring ? '正在创建配置…' : `基于${selectedTemplate ? `「${selectedTemplate.name}」` : '当前流水线'}配置本书`}
              </button>
            </div>
          ) : (
            <div className="studio-wizard-fields">
              <label htmlFor="studio-wizard-idea">创作想法</label>
              <textarea
                autoFocus
                id="studio-wizard-idea"
                maxLength={4000}
                onChange={(event) => setState((current) => wizardWithIdea(current, event.target.value))}
                placeholder="用一段话写下题材、人物处境、核心冲突或你最想保留的感觉。正式书名会在创作立项阶段生成。"
                rows={7}
                value={state.idea}
              />
              <small>书名、故事承诺、世界规则和叙事声音会在首阶段形成，可换稿后再确认。</small>
            </div>
          )}
          {state.error ? <p className="studio-inline-error" role="alert">{state.error}</p> : null}
          <div className="studio-wizard-actions">
            <button className="ghost" onClick={state.step === 'workflow' ? close : () => setState(wizardBack)} type="button">
              {state.step === 'workflow' ? '取消' : '上一步'}
            </button>
            <LoadingButton className="tech-button" disabled={state.submitting || (state.step === 'idea' && !wizardCanSubmit(state)) || (state.step === 'workflow' && !state.templateId)} loading={state.submitting} loadingLabel="正在创建" type="submit">
              {primaryLabel}
            </LoadingButton>
          </div>
        </form>
      </section>
    </div>
  );

  if (typeof document === 'undefined') return content;
  return createPortal(content, document.body);
}
