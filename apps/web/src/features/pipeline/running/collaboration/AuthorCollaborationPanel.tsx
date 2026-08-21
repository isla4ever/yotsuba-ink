import { Archive, Database, History, Pencil, Sparkles, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { CollaborationStageId, SelectionAnchor } from "../../contracts/authorCollaboration"
import type { KnowledgeDocument } from "../../contracts/knowledge"
import { collaborationStageLabels, shortProviderLabel } from '../../lib/authorCollaborationProjection';
import type { AuthorCollaborationController } from '../../state/useAuthorCollaboration';
import { CollaborationHistoryDrawer } from './CollaborationHistoryDrawer';
import { CollaborationThread } from './CollaborationThread';
import { ContextReceiptDialog } from './ContextReceiptDialog';

type Props = {
  canRevise: boolean;
  collaboration: AuthorCollaborationController;
  knowledgeDocuments: KnowledgeDocument[];
  onClearSelection: () => void;
  onClose: () => void;
  onOpenKnowledgeManager: () => void;
  selection: SelectionAnchor | null;
  stageId: CollaborationStageId;
};

export function AuthorCollaborationPanel({ canRevise, collaboration, knowledgeDocuments, onClearSelection, onClose, onOpenKnowledgeManager, selection, stageId }: Props) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [titleEditing, setTitleEditing] = useState(false);
  const [title, setTitle] = useState('');
  useEffect(() => {
    setTitle(collaboration.activeThread?.title ?? '');
    setTitleEditing(false);
  }, [collaboration.activeThread?.thread_id, collaboration.activeThread?.title]);
  useEffect(() => {
    if (collaboration.pendingSubmission) setReceiptOpen(true);
  }, [collaboration.pendingSubmission]);

  const saveTitle = () => {
    const trimmed = title.trim();
    if (trimmed && collaboration.activeThread && trimmed !== collaboration.activeThread.title) {
      void collaboration.renameThread(collaboration.activeThread.thread_id, trimmed).catch(() => undefined);
    }
    setTitleEditing(false);
  };
  const archiveBlocked = collaboration.actionPending
    || collaboration.isStreaming
    || collaboration.activeThread?.has_unapplied_patch
    || Boolean(collaboration.composerDraft.trim());
  return (
    <aside
      aria-label="作者协作"
      className="author-collaboration-panel"
      onKeyDown={(event) => {
        if (event.key !== 'Escape') return;
        event.preventDefault();
        event.stopPropagation();
        if (historyOpen) setHistoryOpen(false);
        else onClose();
      }}
    >
      <header className="collaboration-panel-header">
        <div className="collaboration-panel-identity">
          <span><Sparkles size={15} />{collaborationStageLabels[stageId]}</span>
          {titleEditing ? (
            <input aria-label="对话标题" autoFocus maxLength={120} onBlur={saveTitle} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') saveTitle(); if (event.key === 'Escape') { event.stopPropagation(); setTitleEditing(false); } }} value={title} />
          ) : (
            <button className="collaboration-title" onClick={() => setTitleEditing(true)} type="button"><strong>{collaboration.activeThread?.title ?? '作者协作'}</strong><Pencil size={12} /></button>
          )}
          <small>{collaboration.composerDraft.trim() ? `未发送草稿已保留 · ${shortProviderLabel(collaboration.detail)}` : shortProviderLabel(collaboration.detail)}</small>
        </div>
        <div className="collaboration-panel-actions">
          <button aria-label="查看上下文回执" disabled={!collaboration.latestReceipt} onClick={() => setReceiptOpen(true)} title="上下文回执" type="button"><Database size={15} /></button>
          <button aria-label="对话历史" onClick={() => setHistoryOpen((open) => !open)} title="对话历史" type="button"><History size={15} /></button>
          <button aria-label="归档当前对话" disabled={!collaboration.activeThread || archiveBlocked} onClick={() => { if (collaboration.activeThread) void collaboration.archiveThread(collaboration.activeThread.thread_id); }} title={collaboration.composerDraft.trim() ? '先发送或清空未发送草稿' : collaboration.activeThread?.has_unapplied_patch ? '先处理未决改稿' : '归档'} type="button"><Archive size={15} /></button>
          <button aria-label="关闭作者协作" onClick={onClose} title="关闭" type="button"><X size={17} /></button>
        </div>
      </header>
      {collaboration.notice ? <div className="collaboration-notice" role="status">{collaboration.notice}</div> : null}
      {collaboration.error ? <div className="collaboration-error" role="alert"><span>{collaboration.error}</span><button aria-label="关闭错误" onClick={collaboration.clearError} type="button"><X size={13} /></button></div> : null}
      {collaboration.activeThread?.status === 'archived' ? <div className="collaboration-readonly-banner">这段历史对话已归档，可阅读但不能继续发送。</div> : null}
      <CollaborationThread
        canRevise={canRevise}
        collaboration={collaboration}
        knowledgeDocuments={knowledgeDocuments}
        onClearSelection={onClearSelection}
        onOpenKnowledgeManager={onOpenKnowledgeManager}
        onOpenReceipt={() => setReceiptOpen(true)}
        selection={selection}
      />
      <CollaborationHistoryDrawer
        activeThreadId={collaboration.activeThreadId}
        disabled={collaboration.actionPending || collaboration.isStreaming}
        hasDraft={collaboration.hasComposerDraft}
        onArchive={(threadId) => { void collaboration.archiveThread(threadId); }}
        onClose={() => setHistoryOpen(false)}
        onDelete={(threadId) => { void collaboration.deleteThread(threadId); }}
        onNew={() => { void collaboration.newThread(); setHistoryOpen(false); }}
        onSwitch={(threadId) => { collaboration.switchThread(threadId); setHistoryOpen(false); }}
        open={historyOpen}
        threads={collaboration.threads}
      />
      <ContextReceiptDialog
        confirmPending={Boolean(collaboration.pendingSubmission)}
        disabled={collaboration.actionPending}
        onCancelPending={() => {
          collaboration.dismissPendingSubmission();
          setReceiptOpen(false);
        }}
        onConfirm={() => { void collaboration.confirmPendingSubmission().then(() => setReceiptOpen(false)); }}
        onOpenChange={setReceiptOpen}
        open={receiptOpen}
        pendingMessage={collaboration.pendingSubmission?.input.message}
        receipt={collaboration.pendingSubmission?.receipt ?? collaboration.latestReceipt}
      />
    </aside>
  );
}
