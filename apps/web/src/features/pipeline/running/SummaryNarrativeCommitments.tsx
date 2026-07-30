import { CheckCircle2, Edit3, ShieldCheck, Swords, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import type { QualityMode } from '../contracts';
import type { SummaryArtifact } from './stageArtifacts';
import { ArtifactDraftActions } from './ArtifactDraftActions';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, normalizedDraftLines, requiredDraftFieldErrors } from './artifactDraftValidation';

type Props = {
  artifact: SummaryArtifact;
  onChange: (patch: Pick<SummaryArtifact, 'core_conflict' | 'ending_resolution' | 'consistency_checks'>) => void;
  qualityMode: QualityMode;
  readOnly: boolean;
};

export function SummaryNarrativeCommitments({ artifact, onChange, qualityMode, readOnly }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <section className="summary-narrative-commitments">
      <button onClick={() => setOpen(true)} type="button">
        <i><Swords size={14} /></i>
        <span><small>主线冲突</small><strong>{artifact.core_conflict || '待补充'}</strong></span>
      </button>
      <button onClick={() => setOpen(true)} type="button">
        <i><CheckCircle2 size={14} /></i>
        <span><small>结局承诺</small><strong>{artifact.ending_resolution || '待补充'}</strong></span>
      </button>
      <button onClick={() => setOpen(true)} type="button">
        <i><ShieldCheck size={14} /></i>
        <span><small>一致性检查</small><strong>{artifact.consistency_checks.length} 项已记录</strong></span>
        <Edit3 size={13} />
      </button>
      <AnimatePresence>
        {open ? (
          <SummaryCommitmentDialog
            artifact={artifact}
            onClose={() => setOpen(false)}
            onSave={(patch) => {
              onChange(patch);
              setOpen(false);
            }}
            qualityMode={qualityMode}
            readOnly={readOnly}
          />
        ) : null}
      </AnimatePresence>
    </section>
  );
}

function SummaryCommitmentDialog({
  artifact,
  onClose,
  onSave,
  qualityMode,
  readOnly,
}: {
  artifact: SummaryArtifact;
  onClose: () => void;
  onSave: Props['onChange'];
  qualityMode: QualityMode;
  readOnly: boolean;
}) {
  const [initialValues] = useState(() => ({
    checks: artifact.consistency_checks.join('\n'),
    coreConflict: artifact.core_conflict,
    endingResolution: artifact.ending_resolution,
  }));
  const [coreConflict, setCoreConflict] = useState(artifact.core_conflict);
  const [endingResolution, setEndingResolution] = useState(artifact.ending_resolution);
  const [checks, setChecks] = useState(artifact.consistency_checks.join('\n'));
  const dirty = !draftsEqual(initialValues, { checks, coreConflict, endingResolution });
  const errors = requiredDraftFieldErrors([
    { key: 'coreConflict', label: '主线冲突', value: coreConflict },
    { key: 'endingResolution', label: '结局承诺', value: endingResolution },
    { key: 'checks', label: '一致性检查', value: normalizedDraftLines(checks).join('\n') },
  ]);
  const invalidCount = draftErrorCount(errors);
  const scopeLabel = '叙事承诺当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });
  return (
    <>
      {createPortal(
    <motion.div animate="animate" className={`app-overlay-backdrop summary-commitment-backdrop mode-${qualityMode}`} exit="exit" initial="initial" onClick={requestClose} variants={backdropMotionVariants}>
      <motion.section
        animate="animate"
        aria-label={readOnly ? '预览叙事承诺' : '编辑叙事承诺'}
        aria-modal="true"
        className={`app-dialog-surface summary-commitment-dialog${readOnly ? ' readonly' : ''}`}
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <header>
          <div><p className="eyebrow">叙事承诺</p><h2>主线冲突与结局承诺</h2></div>
          <button aria-label="关闭叙事承诺" className="modal-close" onClick={requestClose} type="button"><X size={18} /></button>
        </header>
        <div className="summary-commitment-fields">
          <ArtifactDraftField error={errors.coreConflict} id="summary-core-conflict" label="主线冲突" required>
            {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={coreConflict} onChange={(event) => setCoreConflict(event.target.value)} />}
          </ArtifactDraftField>
          <ArtifactDraftField error={errors.endingResolution} id="summary-ending-resolution" label="结局承诺" required>
            {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={endingResolution} onChange={(event) => setEndingResolution(event.target.value)} />}
          </ArtifactDraftField>
          <ArtifactDraftField
            error={errors.checks}
            hint="每行一项，记录与 Info 人物、世界观硬规则和关键物证的对齐结果。"
            id="summary-consistency-checks"
            label="一致性检查"
            required
          >
            {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={checks} onChange={(event) => setChecks(event.target.value)} />}
          </ArtifactDraftField>
        </div>
        {readOnly ? null : (
          <ArtifactDraftActions
            dirty={dirty}
            invalidCount={invalidCount}
            onClose={requestClose}
            onSave={() => onSave({
              consistency_checks: normalizedDraftLines(checks),
              core_conflict: coreConflict.trim(),
              ending_resolution: endingResolution.trim(),
            })}
          />
        )}
      </motion.section>
    </motion.div>,
    document.body,
      )}
      {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={`mode-${qualityMode}`} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}
