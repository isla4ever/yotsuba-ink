import { ArrowLeft, FilePlus2, Layers, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { WorkflowStage } from '../../contracts';
import { CreationModeSetupSection } from '../../planning/CreationModeSetupSection';
import { StageInspector } from '../../planning/StageInspector';
import { ManuscriptLoadingIndicator } from '../ManuscriptLoadingIndicator';
import { RevealText } from '../RevealText';
import { defaultTemplateId, templateQualityLabels } from './newProjectWizardModel';
import { useWorkflowTemplateEditor, type TemplateEditorSaveState } from './useWorkflowTemplateEditor';

type Props = { workflowId: string };

/**
 * Full-page workflow template editor. The studio list only names templates; the
 * stage chain, per-stage parameters and model bindings are edited here, on the
 * same StageInspector the per-book planning surface uses.
 */
export function WorkflowTemplateEditorPage({ workflowId }: Props) {
  const navigate = useNavigate();
  const editor = useWorkflowTemplateEditor(workflowId);
  const [activeStageId, setActiveStageId] = useState('');
  const workflow = editor.workflow;
  const stages = workflow?.nodes ?? [];
  const activeStage: WorkflowStage | undefined = stages.find((stage) => stage.id === activeStageId) ?? stages[0];
  const isDefault = workflowId === defaultTemplateId;

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
            {isDefault
              ? '默认模板是所有新作品的出厂配置：这里的修改会影响之后新建的作品，已建作品保持自己的副本。'
              : '模板在建书时复制一份给作品：这里的修改只影响之后用它新建的作品。'}
          </span>
        </div>
        <dl className="workspace-page-stats">
          <div><dt><Layers size={13} />阶段</dt><dd>{stages.length}</dd></div>
          <div><dt><SlidersHorizontal size={13} />质量档位</dt><dd>{workflow ? templateQualityLabels[workflow.quality_mode] ?? workflow.quality_mode : '—'}</dd></div>
          <div><dt>自动保存</dt><dd>{saveStateLabel(editor.saveState)}</dd></div>
        </dl>
      </header>

      {editor.error ? <p className="studio-inline-error" role="alert">{editor.error}</p> : null}

      {editor.loading || !workflow || !activeStage ? (
        <div className="workflow-editor-loading" role="status">
          <ManuscriptLoadingIndicator size="compact" />
          <span>正在载入工作流模板…</span>
        </div>
      ) : (
        <div className="workflow-editor-layout">
          <div className="workflow-editor-side">
            <section className="workflow-editor-panel">
              <header className="workflow-editor-panel-head">
                <h2>模板信息</h2>
                <span>名称与质量档位</span>
              </header>
              <label className="workflow-editor-field">
                <span>模板名称</span>
                <input
                  disabled={isDefault}
                  maxLength={120}
                  onChange={(event) => editor.renameTemplate(event.target.value)}
                  type="text"
                  value={workflow.name}
                />
              </label>
              {isDefault ? <p className="workflow-editor-note">默认模板名称固定，可复制一份后自由命名。</p> : null}
              <button className="workflow-editor-use" onClick={() => navigate(`/studio?view=templates&new=1&template=${encodeURIComponent(workflow.id)}`)} type="button">
                <FilePlus2 size={14} />用这个模板建书
              </button>
            </section>

            <nav aria-label="阶段链路" className="workflow-editor-panel workflow-editor-stages">
              <header className="workflow-editor-panel-head">
                <h2>阶段链路</h2>
                <span>{stages.length} 个阶段</span>
              </header>
              <ol className="nw-reveal-scroll">
                {stages.map((stage, position) => (
                  <li key={stage.id}>
                    <button
                      aria-current={stage.id === activeStage.id ? 'true' : undefined}
                      className={`workflow-editor-stage${stage.id === activeStage.id ? ' active' : ''}`}
                      onClick={() => setActiveStageId(stage.id)}
                      type="button"
                    >
                      <span className="workflow-editor-stage-ordinal">{position + 1}</span>
                      <span className="workflow-editor-stage-copy">
                        <strong>{stage.label}</strong>
                        <small>{stage.model_settings.model || '继承默认模型'}</small>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            </nav>
          </div>

          <div className="workflow-editor-main">
            <section className="workflow-editor-panel">
              <header className="workflow-editor-panel-head">
                <h2>创作模式</h2>
                <span>决定审核强度与运行界面</span>
              </header>
              <CreationModeSetupSection context="review" value={workflow.quality_mode} onChange={editor.setQualityMode} />
            </section>

            <section className="workflow-editor-panel workflow-editor-inspector">
              <StageInspector
                inputIdPrefix={`template-${workflow.id}`}
                knowledgeDocuments={[]}
                providers={workflow.provider_profiles}
                qualityMode={workflow.quality_mode}
                stage={activeStage}
                onAddModelOption={editor.addModelOption}
                onChange={editor.updateStage}
              />
            </section>
          </div>
        </div>
      )}
    </section>
  );
}

function saveStateLabel(state: TemplateEditorSaveState) {
  return ({ idle: '就绪', saving: '保存中', saved: '已保存', failed: '保存失败' })[state];
}
