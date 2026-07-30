import { X, type LucideIcon } from 'lucide-react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import {
  backdropMotionVariants,
  overlayExitDurationMs,
  sheetMotionVariants,
} from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';

type Props = {
  busy: boolean;
  children: ReactNode;
  icon: LucideIcon;
  onClose: () => void;
  subtitle: string;
  title: string;
};

export function WritingMobileSheet({ busy, children, icon: Icon, onClose, subtitle, title }: Props) {
  const sheetRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.sheet,
    onClose,
    open: true,
    suspended: busy,
  });
  return createPortal(
    <motion.div
      animate="animate"
      className="writing-mobile-sheet-backdrop app-overlay-backdrop"
      exit="exit"
      initial="initial"
      onClick={busy ? undefined : onClose}
      variants={backdropMotionVariants}
    >
      <motion.section
        animate="animate"
        aria-busy={busy}
        aria-label={title}
        aria-modal="true"
        className="writing-mobile-sheet app-sheet-surface"
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={sheetRef}
        role="dialog"
        tabIndex={-1}
        variants={sheetMotionVariants}
      >
        <header className="writing-mobile-sheet-head">
          <div><Icon aria-hidden="true" size={16} /><span><strong>{title}</strong><small>{subtitle}</small></span></div>
          <button aria-label={`关闭${title}`} disabled={busy} onClick={onClose} type="button"><X size={18} /></button>
        </header>
        <div className="writing-mobile-sheet-body">{children}</div>
      </motion.section>
    </motion.div>,
    document.body,
  );
}
