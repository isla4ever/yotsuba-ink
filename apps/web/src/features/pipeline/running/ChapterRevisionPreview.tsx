import { Check, X } from 'lucide-react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import type { ChapterRevisionCandidate } from '../contracts';
import { LoadingButton } from '../layout/LoadingButton';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';

type Props = {
  busy: boolean;
  candidate: ChapterRevisionCandidate;
  error: string;
  onAccept: () => void;
  onClose: () => void;
};

export function ChapterRevisionPreview({ busy, candidate, error, onAccept, onClose }: Props) {
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  return createPortal(
    <motion.div animate="animate" className="app-overlay-backdrop chapter-revision-backdrop" exit="exit" initial="initial" onClick={busy ? undefined : onClose} variants={backdropMotionVariants}>
      <motion.section
        animate="animate"
        aria-busy={busy}
        aria-label="局部修订预览"
        aria-modal="true"
        className="app-dialog-surface chapter-revision-dialog"
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <header>
          <div><small>选区修订</small><strong>{candidate.operation_label}预览</strong></div>
          <button aria-label="关闭修订预览" className="modal-close" disabled={busy} onClick={onClose} type="button"><X size={17} /></button>
        </header>
        <div className="chapter-revision-compare">
          <section><span>修订前</span><p>{candidate.before}</p></section>
          <section><span>候选替换</span><p>{candidate.replacement}</p></section>
        </div>
        {candidate.direction ? <p className="chapter-revision-direction">编辑方向：{candidate.direction}</p> : null}
        {error ? <p className="chapter-revision-error" role="alert">{error}</p> : null}
        <footer>
          <button className="ghost" disabled={busy} onClick={onClose} type="button">放弃候选</button>
          <LoadingButton className="mode-primary-action" loading={busy} loadingLabel="正在创建版本" onClick={onAccept}>
            <Check size={14} />接受并创建新版本
          </LoadingButton>
        </footer>
      </motion.section>
    </motion.div>,
    document.body,
  );
}
