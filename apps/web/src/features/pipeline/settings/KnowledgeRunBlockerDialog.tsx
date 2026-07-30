import { DatabaseZap, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { overlayExitDurationMs } from '../lib/motion';
import { useDialogExitPresence } from '../state/useDialogExitPresence';
import { useOverlayDialog } from '../state/useOverlayDialog';

type Props = {
  message: string;
  onClose: () => void;
  onOpenKnowledge: () => void;
  open: boolean;
};

export function KnowledgeRunBlockerDialog({ message, onClose, onOpenKnowledge, open }: Props) {
  const presence = useDialogExitPresence(open);
  const dialogRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.dialog,
    onClose,
    open: open && presence.presentOpen,
  });
  if (!presence.presentOpen) return null;

  const content = (
    <div
      className={`knowledge-blocker-backdrop app-overlay-backdrop${presence.exiting ? ' is-exiting' : ''}`}
      onClick={(event) => { if (event.currentTarget === event.target) onClose(); }}
      role="presentation"
    >
      <section
        aria-label="知识库启动条件"
        aria-modal="true"
        className="knowledge-blocker-dialog app-dialog-surface"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="knowledge-blocker-head">
          <span aria-hidden="true"><DatabaseZap size={18} /></span>
          <div>
            <p className="eyebrow">启动条件</p>
            <h2>需要先准备项目资料</h2>
          </div>
          <button aria-label="关闭" className="icon-button tech-icon-button" onClick={onClose} type="button"><X size={16} /></button>
        </header>
        <p>{message}</p>
        <div className="knowledge-blocker-actions">
          <button className="tech-button" onClick={onOpenKnowledge} type="button">打开项目资料</button>
          <button className="ghost" onClick={onClose} type="button">稍后处理</button>
        </div>
      </section>
    </div>
  );
  return typeof document === 'undefined' ? content : createPortal(content, document.body);
}
