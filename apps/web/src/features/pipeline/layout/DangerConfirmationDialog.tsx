import { TriangleAlert } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useId } from 'react';
import { createPortal } from 'react-dom';
import { backdropMotionVariants, dialogMotionVariants, overlayExitDurationMs } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { LoadingButton } from './LoadingButton';

type Props = {
  busy?: boolean;
  busyLabel?: string;
  confirmLabel: string;
  description: string;
  details?: string[];
  modeClass?: string;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  title: string;
};

export function DangerConfirmationDialog({
  busy = false,
  busyLabel = '处理中',
  confirmLabel,
  description,
  details = [],
  modeClass = '',
  onCancel,
  onConfirm,
  open,
  title,
}: Props) {
  const titleId = useId();
  const descriptionId = useId();
  const close = () => {
    if (!busy) onCancel();
  };
  const dialogRef = useOverlayDialog<HTMLElement>({ exitDurationMs: overlayExitDurationMs.dialog, onClose: close, open });

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className={`app-overlay-backdrop danger-confirmation-backdrop ${modeClass}`}
          exit="exit"
          initial="initial"
          onClick={(event) => {
            if (event.currentTarget === event.target) close();
          }}
          role="presentation"
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            aria-describedby={descriptionId}
            aria-busy={busy}
            aria-labelledby={titleId}
            aria-modal="true"
            className="app-dialog-surface danger-confirmation-dialog"
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            ref={dialogRef}
            role="alertdialog"
            tabIndex={-1}
            variants={dialogMotionVariants}
          >
            <span aria-hidden="true" className="danger-confirmation-icon"><TriangleAlert size={20} /></span>
            <div>
              <h2 id={titleId}>{title}</h2>
              <p id={descriptionId}>{description}</p>
              {details.length ? (
                <ul>{details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
              ) : null}
            </div>
            <footer>
              <button className="ghost" disabled={busy} onClick={close} type="button">取消</button>
              <LoadingButton className="danger-action" disabled={busy} loading={busy} loadingLabel={busyLabel} onClick={onConfirm}>
                {confirmLabel}
              </LoadingButton>
            </footer>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
