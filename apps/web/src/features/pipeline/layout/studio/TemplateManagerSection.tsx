import { Copy, FilePlus2, PencilLine, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { WorkflowDefinition } from '../../contracts';
import { LoadingButton } from '../LoadingButton';
import { defaultTemplateId, templateSummaryLine } from './newProjectWizardModel';

type Props = {
  templates: WorkflowDefinition[];
  error: string;
  onDuplicate: (workflowId: string, name: string) => Promise<void>;
  onRename: (template: WorkflowDefinition, name: string) => Promise<void>;
  onDelete: (workflowId: string) => Promise<void>;
  onUse: (workflowId: string) => void;
};

/**
 * Studio main-area template management (kept beside the card wall instead of a
 * separate sidebar surface, so template copy → new-project flows stay on one page).
 */
export function TemplateManagerSection({ templates, error, onDuplicate, onRename, onDelete, onUse }: Props) {
  const [renamingId, setRenamingId] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [pendingAction, setPendingAction] = useState('');

  const runAction = async (id: string, kind: 'copy' | 'delete' | 'rename', action: () => Promise<void>) => {
    setPendingAction(`${kind}:${id}`);
    try {
      await action();
    } finally {
      setPendingAction('');
    }
  };

  return (
    <section aria-labelledby="studio-templates-heading" className="studio-templates" id="studio-templates">
      <div className="studio-section-head">
        <h2 id="studio-templates-heading">工作流模板</h2>
        <p>新建作品时从模板复制专属工作流；默认工作流始终可用。</p>
      </div>
      {error ? <p className="studio-inline-error" role="alert">{error}</p> : null}
      <div className="studio-template-list">
        {templates.map((template) => {
          const isDefault = template.id === defaultTemplateId;
          const renaming = renamingId === template.id;
          const busy = pendingAction.endsWith(`:${template.id}`);
          return (
            <article className="studio-template-card" key={template.id}>
              <div className="studio-template-info">
                {renaming ? (
                  <input
                    aria-label={`重命名模板 ${template.name}`}
                    autoFocus
                    maxLength={120}
                    onChange={(event) => setRenameValue(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        setRenamingId('');
                        void runAction(template.id, 'rename', () => onRename(template, renameValue));
                      }
                      if (event.key === 'Escape') setRenamingId('');
                    }}
                    type="text"
                    value={renameValue}
                  />
                ) : (
                  <strong>{template.name}</strong>
                )}
                <span>{templateSummaryLine(template)}{isDefault ? ' · 默认模板' : ''}</span>
              </div>
              <div className="studio-template-actions">
                <button className="ghost" disabled={busy} onClick={() => onUse(template.id)} title="使用此模板新建作品" type="button">
                  <FilePlus2 aria-hidden="true" size={14} />使用
                </button>
                <LoadingButton
                  className="ghost"
                  disabled={busy}
                  loading={pendingAction === `copy:${template.id}`}
                  loadingLabel="复制中"
                  onClick={() => void runAction(template.id, 'copy', () => onDuplicate(template.id, `${template.name} 副本`))}
                  title="复制为新模板"
                >
                  <Copy aria-hidden="true" size={14} />复制
                </LoadingButton>
                {isDefault ? null : (
                  <>
                    <LoadingButton
                      className="ghost"
                      disabled={busy}
                      loading={pendingAction === `rename:${template.id}`}
                      loadingLabel="保存中"
                      onClick={() => {
                        if (renaming) {
                          setRenamingId('');
                          void runAction(template.id, 'rename', () => onRename(template, renameValue));
                        } else {
                          setRenamingId(template.id);
                          setRenameValue(template.name);
                        }
                      }}
                      title="重命名模板"
                    >
                      <PencilLine aria-hidden="true" size={14} />{renaming ? '保存' : '重命名'}
                    </LoadingButton>
                    <LoadingButton
                      className="ghost danger"
                      disabled={busy}
                      loading={pendingAction === `delete:${template.id}`}
                      loadingLabel="删除中"
                      onClick={() => void runAction(template.id, 'delete', () => onDelete(template.id))}
                      title="删除模板（被作品引用时会被拒绝）"
                    >
                      <Trash2 aria-hidden="true" size={14} />删除
                    </LoadingButton>
                  </>
                )}
              </div>
            </article>
          );
        })}
        {templates.length === 0 ? <p className="studio-wizard-hint">暂无自定义模板；在作品侧栏使用「另存为模板」即可创建。</p> : null}
      </div>
    </section>
  );
}
