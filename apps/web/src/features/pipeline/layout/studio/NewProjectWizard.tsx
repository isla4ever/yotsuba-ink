import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ProjectRecord, QualityMode, WorkflowDefinition } from '../../contracts';
import { LoadingButton } from '../LoadingButton';
import { overlayExitDurationMs } from '../../lib/motion';
import { useOverlayDialog } from '../../state/useOverlayDialog';
import { useDialogExitPresence } from '../../state/useDialogExitPresence';
import {
  initialWizardState,
  templateSummaryLine,
  wizardBack,
  wizardCanSubmit,
  wizardContinue,
  wizardNeedsTemplateStep,
  wizardSelectTemplate,
  wizardWithBasics,
  type NewProjectWizardState,
} from './newProjectWizardModel';

type Props = {
  open: boolean;
  initialTemplateId?: string;
  templates: WorkflowDefinition[];
  qualityMode?: QualityMode;
  onClose: () => void;
  onCreate: (input: { title: string; summary: string; templateId: string }) => Promise<ProjectRecord>;
  onCreated: (project: ProjectRecord) => void;
};

/**
 * New-project wizard. With a real template choice it runs two steps
 * (① title + one-line summary, ② workflow template); with a single template
 * (B4) step ① creates directly — no template screen.
 */
export function NewProjectWizard({ open, initialTemplateId = '', templates, qualityMode = 'balanced', onClose, onCreate, onCreated }: Props) {
  const freshState = () => initialTemplateId ? wizardSelectTemplate(initialWizardState(), initialTemplateId) : initialWizardState();
  const [state, setState] = useState(freshState);
  const presence = useDialogExitPresence(open);
  const dialogRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.dialog,
    initialFocusSelector: '#studio-wizard-title',
    onClose,
    open: open && presence.presentOpen,
  });
  const needsTemplateStep = wizardNeedsTemplateStep(templates);

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
      const project = await onCreate({ summary: source.summary, templateId: source.templateId, title: source.title });
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

  // B4: with no real template choice the continue lands submit-ready and we
  // create immediately instead of showing the template step.
  const advance = () => {
    if (state.submitting) return;
    if (state.step === 'template') {
      void submit(state);
      return;
    }
    const next = wizardContinue(state, templates);
    if (!needsTemplateStep && wizardCanSubmit(next)) {
      void submit(next);
      return;
    }
    setState(next);
  };

  const primaryLabel = state.step === 'template' || !needsTemplateStep
      ? '创建并进入作品'
      : '下一步';

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
        {/* E8: 表单包裹让书名/概要回车即可前进或直接创建。 */}
        <form onSubmit={(event) => { event.preventDefault(); advance(); }}>
          <p className="eyebrow">{stepEyebrow(state.step, needsTemplateStep)}</p>
          <h2>{state.step === 'basics' ? '给作品起个名字' : '选择工作流模板'}</h2>
          {state.step === 'basics' ? (
            <div className="studio-wizard-fields">
              <label htmlFor="studio-wizard-title">书名（必填）</label>
              <input
                id="studio-wizard-title"
                maxLength={120}
                onChange={(event) => setState((current) => wizardWithBasics(current, { title: event.target.value }))}
                placeholder="例如：雾港旧声"
                type="text"
                value={state.title}
              />
              <label htmlFor="studio-wizard-summary">一句概要（可选）</label>
              <input
                id="studio-wizard-summary"
                maxLength={200}
                onChange={(event) => setState((current) => wizardWithBasics(current, { summary: event.target.value }))}
                placeholder="一句话说明这本书讲什么"
                type="text"
                value={state.summary}
              />
            </div>
          ) : (
            <div aria-label="工作流模板" className="studio-wizard-templates" role="radiogroup">
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
                  {template.id === 'default-novel-workflow' ? <em>默认</em> : null}
                </button>
              ))}
              {templates.length === 0 ? <p className="studio-wizard-hint">模板列表加载中，可直接使用默认工作流。</p> : null}
            </div>
          )}
          {state.error ? <p className="studio-inline-error" role="alert">{state.error}</p> : null}
          <div className="studio-wizard-actions">
            <button className="ghost" onClick={state.step === 'basics' ? close : () => setState(wizardBack)} type="button">
              {state.step === 'basics' ? '取消' : '上一步'}
            </button>
            <LoadingButton className="tech-button" disabled={state.submitting || (state.step === 'template' && !wizardCanSubmit(state))} loading={state.submitting} loadingLabel="正在创建" type="submit">
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

function stepEyebrow(step: NewProjectWizardState['step'], needsTemplateStep: boolean) {
  if (!needsTemplateStep) return '新建作品';
  return step === 'basics' ? '第 1 步 / 共 2 步' : '第 2 步 / 共 2 步';
}
