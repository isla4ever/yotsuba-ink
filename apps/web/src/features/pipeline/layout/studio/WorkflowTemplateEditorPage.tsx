import { ArrowLeft, BookmarkPlus, FilePlus2, Layers, SlidersHorizontal } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { WorkflowStage } from '../../contracts';
import { StageInspector } from '../../planning/StageInspector';
import { ManuscriptLoadingIndicator } from '../ManuscriptLoadingIndicator';
import { RevealText } from '../RevealText';
import { templateQualityLabels } from './newProjectWizardModel';
import { useWorkflowTemplateEditor, type TemplateEditorSaveState } from './useWorkflowTemplateEditor';
import { isOfficialWorkflowId, isOneTimeWorkflowId } from '../../lib/officialWorkflows';
import { WorkflowModeControl } from './WorkflowModeControl';
import { WorkflowTemplateDeck } from './WorkflowTemplateDeck';
import { contentSwapMotionVariants } from '../../lib/motion';

type Props = { workflowId: string };

/**
 * Full-page workflow template editor. The studio list only names templates; the
 * stage chain, per-stage parameters and model bindings are edited here. Book
 * preparation deliberately has no stage-chain editor.
 */
export function WorkflowTemplateEditorPage({ workflowId }: Props) {
  const navigate = useNavigate();
  const editor = useWorkflowTemplateEditor(workflowId);
  const [activeStageId, setActiveStageId] = useState('');
  const [actionState, setActionState] = useState<'idle' | 'copying' | 'saving-template'>('idle');
  const [actionError, setActionError] = useState('');
  const controlBoardRef = useRef<HTMLElement>(null);
  const workflow = editor.workflow;
  const stages = workflow?.nodes ?? [];
  const activeStage: WorkflowStage | undefined = stages.find((stage) => stage.id === activeStageId) ?? stages[0];
  const isOfficial = isOfficialWorkflowId(workflowId);
  const isOneTime = isOneTimeWorkflowId(workflowId);

  useEffect(() => {
    controlBoardRef.current?.scrollTo({ top: 0 });
  }, [activeStage?.id]);

  const configureForBook = async () => {
    if (actionState !== 'idle') return;
    setActionState('copying');
    setActionError('');
    try {
      const draft = await editor.createOneTimeCopy();
      navigate(`/studio/workflow/${encodeURIComponent(draft.id)}`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '创建本书配置失败。');
      setActionState('idle');
    }
  };

  const saveOneTimeAsTemplate = async () => {
    if (!workflow || actionState !== 'idle') return;
    setActionState('saving-template');
    setActionError('');
    try {
      const template = await editor.saveAsTemplate(`${workflow.name.replace('本书专用', '').trim() || '我的创作'}模板`);
      navigate(`/studio/workflow/${encodeURIComponent(template.id)}`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '另存模板失败。');
      setActionState('idle');
    }
  };

  return (
    <section aria-labelledby="workflow-editor-title" className="workflow-editor-page workspace-page">
      <header className="workspace-page-head">
        <div className="workspace-page-title">
          <p className="eyebrow">工作室 · 工作流模板</p>
          <div className="workflow-editor-title-row">
            <button aria-label="返回模板列表" className="workflow-editor-back" onClick={() => navigate('/studio?view=templates')} type="button">
              <ArrowLeft size={15} />
            </button>
            <RevealText as="h1" id="workflow-editor-title" text={workflow?.name || '工作流模板'} />
          </div>
          <span>
            {isOfficial
              ? '官方配置只读，确保三种模式的模型策略稳定；复制为本书配置后可自由调整。'
              : isOneTime
                ? '这份配置只服务下一本书；可直接使用，也可另存为以后复用的模板。'
                : '模板在建书时复制一份给作品：这里的修改只影响之后用它新建的作品。'}
          </span>
        </div>
        <dl className="workspace-page-stats">
          <div><dt><Layers size={13} />阶段</dt><dd>{stages.length}</dd></div>
          <div><dt><SlidersHorizontal size={13} />质量档位</dt><dd>{workflow ? templateQualityLabels[workflow.quality_mode] ?? workflow.quality_mode : '—'}</dd></div>
          <div><dt>{isOfficial ? '配置权限' : '自动保存'}</dt><dd>{isOfficial ? '官方只读' : saveStateLabel(editor.saveState)}</dd></div>
        </dl>
      </header>

      {editor.error ? <p className="studio-inline-error" role="alert">{editor.error}</p> : null}
      {actionError ? <p className="studio-inline-error" role="alert">{actionError}</p> : null}

      {editor.loading || !workflow || !activeStage ? (
        <div className="workflow-editor-loading" role="status">
          <ManuscriptLoadingIndicator size="compact" />
          <span>正在载入工作流模板…</span>
        </div>
      ) : (
        <div className="workflow-editor-layout">
          <section aria-label="工作流阶段全貌" className="workflow-editor-deck-pane">
            <header className="workflow-editor-deck-toolbar">
              <label className="workflow-editor-field">
                <span className="workflow-editor-control-label">
                  <strong>模板名称</strong>
                  <small>{isOneTime ? '仅本书' : isOfficial ? '官方只读' : '自定义模板'}</small>
                </span>
                <input
                  disabled={isOfficial}
                  maxLength={120}
                  onChange={(event) => editor.renameTemplate(event.target.value)}
                  type="text"
                  value={workflow.name}
                />
              </label>
              <WorkflowModeControl readOnly={isOfficial} value={workflow.quality_mode} onChange={editor.setQualityMode} />
              <div className="workflow-editor-action-cluster">
                <span className="workflow-editor-control-label">
                  <strong>使用方式</strong>
                  <small>{isOfficial ? '先复制，再按本书调整' : isOneTime ? '使用或沉淀为模板' : '从模板创建作品'}</small>
                </span>
                <div className="workflow-editor-actions">
                  {isOfficial ? (
                    <button className="workflow-editor-use" disabled={actionState !== 'idle'} onClick={() => void configureForBook()} type="button">
                      <SlidersHorizontal size={14} />{actionState === 'copying' ? '正在创建…' : '配置本书'}
                    </button>
                  ) : (
                    <button className="workflow-editor-use" onClick={() => navigate(`/studio?view=templates&new=1&template=${encodeURIComponent(workflow.id)}`)} type="button">
                      <FilePlus2 size={14} />{isOneTime ? '仅本书使用' : '用这个模板建书'}
                    </button>
                  )}
                  {isOneTime ? (
                    <button className="workflow-editor-use secondary" disabled={actionState !== 'idle'} onClick={() => void saveOneTimeAsTemplate()} type="button">
                      <BookmarkPlus size={14} />{actionState === 'saving-template' ? '正在另存…' : '另存模板'}
                    </button>
                  ) : null}
                </div>
              </div>
            </header>
            <WorkflowTemplateDeck
              activeStageId={activeStage.id}
              qualityMode={workflow.quality_mode}
              stages={stages}
              onSelect={setActiveStageId}
            />
          </section>

          <section aria-label="阶段配置" className="workflow-editor-control-board" ref={controlBoardRef}>
            <AnimatePresence initial={false} mode="wait">
              <motion.div
                animate="animate"
                className="workflow-editor-stage-panel"
                exit="exit"
                initial="initial"
                key={activeStage.id}
                variants={contentSwapMotionVariants}
              >
                <fieldset className="workflow-editor-inspector" disabled={isOfficial}>
                  <StageInspector
                    inputIdPrefix={`template-${workflow.id}`}
                    knowledgeDocuments={[]}
                    providers={workflow.provider_profiles}
                    qualityMode={workflow.quality_mode}
                    readOnly={isOfficial}
                    stage={activeStage}
                    onAddModelOption={editor.addModelOption}
                    onChange={editor.updateStage}
                  />
                </fieldset>
              </motion.div>
            </AnimatePresence>
          </section>
        </div>
      )}
    </section>
  );
}

function saveStateLabel(state: TemplateEditorSaveState) {
  return ({ idle: '就绪', saving: '保存中', saved: '已保存', failed: '保存失败' })[state];
}
