import { X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { ArtifactDraftActions } from './ArtifactDraftActions';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, requiredDraftFieldErrors } from './artifactDraftValidation';

type Props =
  | {
      kind: 'beat';
      index: number;
      onClose: () => void;
      onSave: (value: { title: string; goal: string; turn: string }) => void;
      readOnly?: boolean;
      value: { title: string; goal: string; turn: string };
    }
  | {
      kind: 'turn';
      index: number;
      onClose: () => void;
      onSave: (value: { label: string; detail: string }) => void;
      readOnly?: boolean;
      value: { label: string; detail: string };
    };

export function SummaryMiniEditDialog(props: Props) {
  const title = props.kind === 'beat'
    ? `结构节拍 ${String(props.index + 1).padStart(2, '0')}`
    : `关键转折 ${String(props.index + 1).padStart(2, '0')}`;
  if (props.kind === 'beat') return <SummaryBeatEditDialog {...props} title={title} />;
  return <SummaryTurnEditDialog {...props} title={title} />;
}

function SummaryBeatEditDialog(props: Extract<Props, { kind: 'beat' }> & { title: string }) {
  const [initialValues] = useState(() => structuredClone(props.value));
  const [values, setValues] = useState(() => structuredClone(props.value));
  const dirty = !draftsEqual(initialValues, values);
  const errors = requiredDraftFieldErrors([
    { key: 'title', label: '节拍名称', value: values.title },
    { key: 'goal', label: '推进目标', value: values.goal },
    { key: 'turn', label: '转折落点', value: values.turn },
  ]);
  const invalidCount = draftErrorCount(errors);
  const modeClass = usePortalModeClass();
  const scopeLabel = '结构节拍当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly: props.readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, props.onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });

  return (
    <>
      {createPortal(
        <AnimatePresence>
          <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
            <motion.section
              animate="animate"
              aria-label={props.title}
              aria-modal="true"
              className={`summary-mini-dialog app-dialog-surface beat${props.readOnly ? ' readonly' : ''}`}
              exit="exit"
              initial="initial"
              onClick={(event) => event.stopPropagation()}
              ref={dialogRef}
              role="dialog"
              tabIndex={-1}
              variants={dialogMotionVariants}
            >
              <button aria-label="关闭编辑" className="modal-close" onClick={requestClose} type="button"><X size={20} /></button>
              <div className="summary-mini-head"><span>结构节拍</span><h2>{props.title}</h2></div>
              <div className="summary-editor-sheet beat">
                <div className="summary-editor-object">
                  <b>{String(props.index + 1).padStart(2, '0')}</b>
                  <ArtifactDraftField error={errors.title} id={`summary-beat-${props.index}-title`} label="节拍名称" required>
                    {(controlProps) => <input {...controlProps} readOnly={props.readOnly} value={values.title} onChange={(event) => setValues((current) => ({ ...current, title: event.target.value }))} />}
                  </ArtifactDraftField>
                </div>
                <div className="summary-editor-fields two">
                  <ArtifactDraftField error={errors.goal} id={`summary-beat-${props.index}-goal`} label="推进目标" required>
                    {(controlProps) => <textarea {...controlProps} readOnly={props.readOnly} value={values.goal} onChange={(event) => setValues((current) => ({ ...current, goal: event.target.value }))} />}
                  </ArtifactDraftField>
                  <ArtifactDraftField error={errors.turn} id={`summary-beat-${props.index}-turn`} label="转折落点" required>
                    {(controlProps) => <textarea {...controlProps} readOnly={props.readOnly} value={values.turn} onChange={(event) => setValues((current) => ({ ...current, turn: event.target.value }))} />}
                  </ArtifactDraftField>
                </div>
              </div>
              {props.readOnly ? null : (
                <ArtifactDraftActions
                  className="summary-mini-actions"
                  dirty={dirty}
                  invalidCount={invalidCount}
                  onClose={requestClose}
                  onSave={() => props.onSave({ title: values.title.trim(), goal: values.goal.trim(), turn: values.turn.trim() })}
                />
              )}
            </motion.section>
          </motion.div>
        </AnimatePresence>,
        document.body,
      )}
      {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={modeClass} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}

function SummaryTurnEditDialog(props: Extract<Props, { kind: 'turn' }> & { title: string }) {
  const [initialValues] = useState(() => structuredClone(props.value));
  const [values, setValues] = useState(() => structuredClone(props.value));
  const dirty = !draftsEqual(initialValues, values);
  const errors = requiredDraftFieldErrors([
    { key: 'label', label: '转折标签', value: values.label },
    { key: 'detail', label: '转折说明', value: values.detail },
  ]);
  const invalidCount = draftErrorCount(errors);
  const modeClass = usePortalModeClass();
  const scopeLabel = '关键转折当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly: props.readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, props.onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });

  return (
    <>
      {createPortal(
        <AnimatePresence>
          <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
            <motion.section
              animate="animate"
              aria-label={props.title}
              aria-modal="true"
              className={`summary-mini-dialog app-dialog-surface turn${props.readOnly ? ' readonly' : ''}`}
              exit="exit"
              initial="initial"
              onClick={(event) => event.stopPropagation()}
              ref={dialogRef}
              role="dialog"
              tabIndex={-1}
              variants={dialogMotionVariants}
            >
              <button aria-label="关闭编辑" className="modal-close" onClick={requestClose} type="button"><X size={20} /></button>
              <div className="summary-mini-head"><span>关键转折</span><h2>{props.title}</h2></div>
              <div className="summary-editor-sheet turn">
                <div className="summary-editor-object">
                  <b>{String(props.index + 1).padStart(2, '0')}</b>
                  <ArtifactDraftField error={errors.label} id={`summary-turn-${props.index}-label`} label="转折标签" required>
                    {(controlProps) => <input {...controlProps} readOnly={props.readOnly} value={values.label} onChange={(event) => setValues((current) => ({ ...current, label: event.target.value }))} />}
                  </ArtifactDraftField>
                </div>
                <div className="summary-editor-fields single">
                  <ArtifactDraftField error={errors.detail} id={`summary-turn-${props.index}-detail`} label="转折说明" required>
                    {(controlProps) => <textarea {...controlProps} readOnly={props.readOnly} value={values.detail} onChange={(event) => setValues((current) => ({ ...current, detail: event.target.value }))} />}
                  </ArtifactDraftField>
                </div>
              </div>
              {props.readOnly ? null : (
                <ArtifactDraftActions
                  className="summary-mini-actions"
                  dirty={dirty}
                  invalidCount={invalidCount}
                  onClose={requestClose}
                  onSave={() => props.onSave({ label: values.label.trim(), detail: values.detail.trim() })}
                />
              )}
            </motion.section>
          </motion.div>
        </AnimatePresence>,
        document.body,
      )}
      {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={modeClass} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}

function usePortalModeClass() {
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
