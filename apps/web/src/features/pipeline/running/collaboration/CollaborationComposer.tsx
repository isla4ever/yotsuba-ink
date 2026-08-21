import { ComposerPrimitive } from '@assistant-ui/react';
import { Database, Send, StopCircle, WandSparkles, X } from 'lucide-react';
import type { CollaborationMode, CollaborationContextReceipt, SelectionAnchor } from "../../contracts/authorCollaboration"
import type { KnowledgeDocument } from "../../contracts/knowledge"
import { collaborationModeLabels } from '../../lib/authorCollaborationProjection';
import type { AuthorCollaborationController } from '../../state/useAuthorCollaboration';
import { ContextSourcePicker } from './ContextSourcePicker';

type Props = {
  canRevise: boolean;
  disabled: boolean;
  isStreaming: boolean;
  knowledgeDocuments: KnowledgeDocument[];
  latestReceipt: CollaborationContextReceipt | null;
  mode: CollaborationMode;
  onClearSelection: () => void;
  onDraftChange: (value: string) => void;
  onOpenKnowledgeManager: () => void;
  onModeChange: (mode: CollaborationMode) => void;
  onOpenReceipt: () => void;
  selection: SelectionAnchor | null;
  setContextOption: AuthorCollaborationController['setContextOption'];
  contextPolicy: AuthorCollaborationController['contextPolicy'];
  toggleKnowledgeSource: AuthorCollaborationController['toggleKnowledgeSource'];
};

export function CollaborationComposer({ canRevise, contextPolicy, disabled, isStreaming, knowledgeDocuments, latestReceipt, mode, onClearSelection, onDraftChange, onModeChange, onOpenKnowledgeManager, onOpenReceipt, selection, setContextOption, toggleKnowledgeSource }: Props) {
  return (
    <ComposerPrimitive.Root className="collaboration-composer">
      {selection ? (
        <div className="collaboration-selection-chip">
          <WandSparkles size={13} />
          <span>已引用 “{selection.preview}”</span>
          <small>{selection.selected_char_count} 字 · {selection.field_path}</small>
          <button aria-label="移除选区" onClick={onClearSelection} type="button"><X size={13} /></button>
        </div>
      ) : null}
      <ComposerPrimitive.Input
        aria-label="作者协作输入"
        cancelOnEscape={false}
        className="collaboration-composer-input"
        disabled={disabled}
        onChange={(event) => onDraftChange(event.target.value)}
        placeholder="说清你想推敲的问题、目标或改稿方向..."
        submitMode="ctrlEnter"
      />
      <div className="collaboration-composer-tools">
        <div aria-label="协作模式" className="collaboration-mode-switch" role="group">
          {(['discuss', 'plan', 'revise'] as CollaborationMode[]).map((value) => (
            <button
              aria-pressed={mode === value}
              className={mode === value ? 'active' : ''}
              disabled={disabled || (value === 'revise' && (!canRevise || !selection))}
              key={value}
              onClick={() => onModeChange(value)}
              title={value === 'revise' && !canRevise ? '正式版本需走修订分支，当前不可原地改稿' : value === 'revise' && !selection ? '先选择一段合法字段文字' : undefined}
              type="button"
            >{collaborationModeLabels[value]}</button>
          ))}
        </div>
        <div className="collaboration-context-tools">
          <ContextSourcePicker
            disabled={disabled || isStreaming}
            knowledgeDocuments={knowledgeDocuments}
            onKnowledgeToggle={toggleKnowledgeSource}
            onOpenKnowledgeManager={onOpenKnowledgeManager}
            onOptionChange={setContextOption}
            policy={contextPolicy}
          />
          <button aria-label="查看上下文回执" disabled={!latestReceipt} onClick={onOpenReceipt} title="上下文回执" type="button"><Database size={15} /></button>
          <span>{latestReceipt ? `约 ${latestReceipt.token_estimate.toLocaleString()} tokens` : '发送前预检上下文'}</span>
        </div>
        {isStreaming ? (
          <ComposerPrimitive.Cancel aria-label="停止生成" className="collaboration-send stop" title="停止生成"><StopCircle size={17} /></ComposerPrimitive.Cancel>
        ) : (
          <ComposerPrimitive.Send aria-label="发送" className="collaboration-send" title="发送（Command/Ctrl + Enter）"><Send size={17} /></ComposerPrimitive.Send>
        )}
      </div>
    </ComposerPrimitive.Root>
  );
}
