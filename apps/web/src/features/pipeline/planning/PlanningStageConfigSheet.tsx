import { SlidersHorizontal, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { backdropMotionVariants, overlayExitDurationMs, sheetMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';

type Props = {
  children: ReactNode;
  onClose: () => void;
  open: boolean;
  stageLabel: string;
};

export function PlanningStageConfigSheet({ children, onClose, open, stageLabel }: Props) {
  const sheetRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.sheet,
    onClose,
    open,
  });

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className="planning-config-sheet-backdrop app-overlay-backdrop"
          exit="exit"
          initial="initial"
          onClick={onClose}
          role="presentation"
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            aria-label={`${stageLabel}阶段配置`}
            aria-modal="true"
            className="planning-config-sheet app-sheet-surface"
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            ref={sheetRef}
            role="dialog"
            tabIndex={-1}
            variants={sheetMotionVariants}
          >
            <header className="planning-config-sheet-head">
              <div>
                <p><SlidersHorizontal size={14} />阶段设置</p>
                <h2>{stageLabel}</h2>
              </div>
              <button aria-label="关闭阶段配置" className="planning-config-sheet-close" onClick={onClose} type="button">
                <X size={19} />
              </button>
            </header>
            <div className="planning-config-sheet-scroll">{children}</div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
