import { X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import type { OutlineBaseline } from './outlineArtifactModel';
import type { OutlineArtifact } from './stageArtifacts';
import { ArtifactDraftActions } from './ArtifactDraftActions';

export type OutlineVolume = OutlineArtifact['volumes'][number];

export type OutlineDependencyDialogProps = {
  baseline: OutlineBaseline;
  onClose: () => void;
  onSave: (values: Partial<Pick<OutlineVolume, 'character_progression' | 'world_reveal' | 'foreshadow_plan'>>) => void;
  readOnly?: boolean;
  volume: OutlineVolume;
};

export function OutlineDependencyDialogShell({ children, icon, kicker, modeClass, onClose, readOnly = false, suspended = false, title }: {
  children: ReactNode;
  icon: ReactNode;
  kicker: string;
  modeClass?: string;
  onClose: () => void;
  readOnly?: boolean;
  suspended?: boolean;
  title: string;
}) {
  const portalModeClass = useOutlinePortalModeClass();
  const resolvedModeClass = modeClass ?? portalModeClass;
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true, suspended });
  return createPortal(
    <AnimatePresence>
      <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${resolvedModeClass}`} exit="exit" initial="initial" onClick={onClose} role="presentation" variants={backdropMotionVariants}>
        <motion.section
          animate="animate"
          aria-label={title}
          aria-modal="true"
          className={`outline-dependency-dialog app-dialog-surface${readOnly ? ' readonly' : ''}`}
          exit="exit"
          initial="initial"
          onClick={(event) => event.stopPropagation()}
          ref={dialogRef}
          role="dialog"
          tabIndex={-1}
          variants={dialogMotionVariants}
        >
          <button aria-label={`关闭${title}`} className="modal-close" onClick={onClose} type="button"><X size={21} /></button>
          <header className="outline-dependency-head">
            <div className="outline-dependency-icon">{icon}</div>
            <div><p className="eyebrow">{kicker}</p><h2>{title}</h2></div>
          </header>
          {children}
        </motion.section>
      </motion.div>
    </AnimatePresence>,
    document.body,
  );
}

export function OutlineDependencyDialogFooter({ dirty = false, disabled = false, invalidCount = 0, label, onClose, onSave, readOnly = false }: {
  dirty?: boolean;
  disabled?: boolean;
  invalidCount?: number;
  label: string;
  onClose: () => void;
  onSave: () => void;
  readOnly?: boolean;
}) {
  if (readOnly) return null;
  return (
    <ArtifactDraftActions
      className="outline-dependency-actions"
      disabled={disabled}
      dirty={dirty}
      invalidCount={invalidCount}
      label={label}
      onClose={onClose}
      onSave={onSave}
    />
  );
}

export function useOutlinePortalModeClass() {
  const [modeClass] = useState(() => {
    if (typeof document === 'undefined') return '';
    const shell = document.querySelector('.product-shell');
    if (shell?.classList.contains('mode-fast')) return 'mode-fast';
    if (shell?.classList.contains('mode-balanced')) return 'mode-balanced';
    if (shell?.classList.contains('mode-deep')) return 'mode-deep';
    return '';
  });
  return modeClass;
}
