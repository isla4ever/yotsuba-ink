import { CheckCircle2, History, X } from 'lucide-react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import type { WorkflowStage } from '../contracts';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { InfoCandidateSummary } from './InfoCandidateSummary';
import type { StageDraftCandidate } from './stageCandidateModel';

type Props = {
  candidates: StageDraftCandidate[];
  onClose: () => void;
  onSelect: (candidateId: string) => void;
  stage: WorkflowStage;
};

export function StageCandidateHistoryDialog({ candidates, onClose, onSelect, stage }: Props) {
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  return createPortal(
    <motion.div animate="animate" className="app-overlay-backdrop candidate-history-backdrop" exit="exit" initial="initial" onClick={onClose} variants={backdropMotionVariants}>
      <motion.section
        animate="animate"
        aria-label={`${stage.label}历史候选`}
        aria-modal="true"
        className="app-dialog-surface candidate-history-dialog"
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <header>
          <span><History size={16} />历史候选</span>
          <button aria-label="关闭历史候选" className="modal-close" onClick={onClose} type="button"><X size={18} /></button>
        </header>
        <div className="candidate-history-list">
          {candidates.map((candidate) => (
            <article key={candidate.id}>
              <small>{candidate.label}</small>
              {stage.type === 'info_recommend' ? (
                <InfoCandidateSummary artifact={candidate.artifact} fallbackPreview={candidate.preview} stage={stage} />
              ) : (
                <><strong>{candidate.title || stage.label}</strong><p>{candidate.preview}</p></>
              )}
              <button className="mode-primary-action" onClick={() => onSelect(candidate.id)} type="button">
                <CheckCircle2 size={14} />恢复此稿
              </button>
            </article>
          ))}
        </div>
      </motion.section>
    </motion.div>,
    document.body,
  );
}
