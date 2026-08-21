import { Archive, MessageSquarePlus, Trash2, X } from 'lucide-react';
import type { CollaborationStageId, CollaborationThread } from "../../contracts/authorCollaboration"
import { collaborationStageLabels } from '../../lib/authorCollaborationProjection';

type Props = {
  activeThreadId: string;
  disabled: boolean;
  hasDraft: (threadId: string) => boolean;
  onArchive: (threadId: string) => void;
  onClose: () => void;
  onDelete: (threadId: string) => void;
  onNew: () => void;
  onSwitch: (threadId: string) => void;
  open: boolean;
  threads: CollaborationThread[];
};

export function CollaborationHistoryDrawer({ activeThreadId, disabled, hasDraft, onArchive, onClose, onDelete, onNew, onSwitch, open, threads }: Props) {
  if (!open) return null;
  return (
    <aside aria-label="协作历史" className="collaboration-history-drawer">
      <header><div><span>对话历史</span><strong>{threads.length} 个线程</strong></div><button aria-label="关闭历史" onClick={onClose} type="button"><X size={16} /></button></header>
      <button className="collaboration-new-thread" disabled={disabled} onClick={onNew} type="button"><MessageSquarePlus size={15} />新建本阶段对话</button>
      <div className="collaboration-history-list">
        {groupThreads(threads).map(([stageId, records]) => (
          <section key={stageId}>
            <h3>{collaborationStageLabels[stageId]}</h3>
            {records.map((thread) => (
              <article className={thread.thread_id === activeThreadId ? 'active' : ''} data-status={thread.status} key={thread.thread_id}>
                <button className="collaboration-history-main" onClick={() => onSwitch(thread.thread_id)} type="button">
                  <strong>{thread.title}</strong>
                  <span>{thread.provider_binding.model} · {formatTime(thread.updated_at)}</span>
                  {thread.has_unapplied_patch ? <small>有一份改稿等待决定</small> : hasDraft(thread.thread_id) ? <small>有未发送草稿</small> : null}
                </button>
                {thread.status === 'active' ? (
                  <div className="collaboration-history-actions">
                    <button aria-label="归档对话" disabled={disabled || hasDraft(thread.thread_id) || thread.has_unapplied_patch} onClick={() => onArchive(thread.thread_id)} title={hasDraft(thread.thread_id) ? '先发送或清空未发送草稿' : thread.has_unapplied_patch ? '先处理未决改稿' : '归档'} type="button"><Archive size={13} /></button>
                    <button aria-label="删除对话" disabled={disabled || hasDraft(thread.thread_id) || thread.has_unapplied_patch} onClick={() => onDelete(thread.thread_id)} title={hasDraft(thread.thread_id) ? '先发送或清空未发送草稿' : thread.has_unapplied_patch ? '先处理未决改稿' : '删除'} type="button"><Trash2 size={13} /></button>
                  </div>
                ) : <span className="collaboration-archived-label">已归档</span>}
              </article>
            ))}
          </section>
        ))}
        {!threads.length ? <p className="collaboration-history-empty">还没有对话记录。</p> : null}
      </div>
    </aside>
  );
}

function groupThreads(threads: CollaborationThread[]) {
  const groups = new Map<CollaborationStageId, CollaborationThread[]>();
  threads.forEach((thread) => groups.set(thread.stage_id, [...(groups.get(thread.stage_id) ?? []), thread]));
  return [...groups.entries()];
}

function formatTime(value: string) {
  const time = new Date(value);
  return Number.isNaN(time.valueOf()) ? value : new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(time);
}
