import { TriangleAlert } from 'lucide-react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import type { UnsavedDraftIntent } from '../state/useUnsavedDraftGuard';

type Props = {
  inline?: boolean;
  intent: UnsavedDraftIntent;
  modeClass?: string;
  onCancel: () => void;
  onDiscard: () => void;
};

export function UnsavedDraftDialog({ inline = false, intent, modeClass = '', onCancel, onDiscard }: Props) {
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: onCancel, open: true });
  const destination = intent.destinationLabel ? `“${intent.destinationLabel}”` : '其他内容';
  const scope = intent.scopeLabel || '当前编辑内容';
  const title = intent.kind === 'switch'
    ? `切换到${destination}？`
    : intent.kind === 'navigate' ? '离开当前页面？' : '放弃未保存的修改？';
  const description = intent.kind === 'switch'
    ? `${scope}尚未保存。继续切换会放弃这些修改。`
    : intent.kind === 'navigate'
      ? `${scope}尚未保存。离开页面会放弃这些修改。`
      : `关闭后，当前修改不会保存到“${intent.scopeLabel || '当前稿'}”。`;

  const dialog = (
    <motion.div
      animate="animate"
      className={`app-overlay-backdrop unsaved-draft-backdrop ${modeClass}`}
      exit="exit"
      initial="initial"
      onClick={onCancel}
      role="presentation"
      variants={backdropMotionVariants}
    >
      <motion.section
        animate="animate"
        aria-describedby="unsaved-draft-description"
        aria-labelledby="unsaved-draft-title"
        aria-modal="true"
        className="app-dialog-surface unsaved-draft-dialog"
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="alertdialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <span className="unsaved-draft-icon" aria-hidden="true"><TriangleAlert size={20} /></span>
        <div>
          <h2 id="unsaved-draft-title">{title}</h2>
          <p id="unsaved-draft-description">{description}</p>
        </div>
        <footer>
          <button className="danger-action" onClick={onDiscard} type="button">放弃修改</button>
          <button className="mode-primary-action" onClick={onCancel} type="button">继续编辑</button>
        </footer>
      </motion.section>
    </motion.div>
  );
  return inline ? dialog : createPortal(dialog, document.body);
}
