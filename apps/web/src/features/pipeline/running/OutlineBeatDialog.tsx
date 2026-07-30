import { X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import type { OutlineArtifact } from './stageArtifacts';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { OUTLINE_BEAT_DEFINITIONS, type OutlineFocusKey } from './outlinePresentation';
import { ArtifactDraftActions } from './ArtifactDraftActions';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, requiredDraftFieldErrors } from './artifactDraftValidation';

type OutlineVolume = OutlineArtifact['volumes'][number];

type OutlineBeatDialogProps = {
  initialFocusKey?: OutlineFocusKey;
  onClose: () => void;
  onSave: (values: Record<string, string>) => void;
  readOnly?: boolean;
  typing?: boolean;
  volume: OutlineVolume;
};

export function OutlineBeatDialog({ initialFocusKey = 'overview', onClose, onSave, readOnly = false, typing = false, volume }: OutlineBeatDialogProps) {
  const [initialValues] = useState(() => volumeValues(volume));
  const [values, setValues] = useState(() => volumeValues(volume));
  const [focusKey, setFocusKey] = useState<OutlineFocusKey>(initialFocusKey);
  const dirty = !draftsEqual(initialValues, values);
  const errors = requiredDraftFieldErrors([
    { key: 'volume_goal', label: '卷目标', value: values.volume_goal },
    { key: 'rhythm', label: '节奏曲线', value: values.rhythm },
    ...OUTLINE_BEAT_DEFINITIONS.map(({ key, label }) => ({ key, label: `${label}节拍`, value: values[key] })),
  ]);
  const invalidCount = draftErrorCount(errors);
  const modeClass = usePortalModeClass();
  const scopeLabel = '分卷节拍当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });
  useEffect(() => setFocusKey(initialFocusKey), [initialFocusKey, volume]);

  const update = (key: string, value: string) => setValues((current) => ({ ...current, [key]: value }));
  const focusField = OUTLINE_BEAT_DEFINITIONS.find(({ key }) => key === focusKey);

  return (
    <>
      {createPortal(
        <AnimatePresence>
          <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
        <motion.section
          animate="animate"
          aria-label={`${volume.title} 结构化大纲`}
          aria-modal="true"
          className={`outline-beat-dialog app-dialog-surface ${typing ? 'typing' : ''}${readOnly ? ' readonly' : ''}`}
          exit="exit"
          initial="initial"
          onClick={(event) => event.stopPropagation()}
          role="dialog"
          ref={dialogRef}
          tabIndex={-1}
          variants={dialogMotionVariants}
        >
          <button aria-label="关闭分卷大纲编辑" className="modal-close" onClick={requestClose} type="button"><X size={21} /></button>
          <header className="outline-beat-dialog-head">
            <div>
              <p className="eyebrow">节拍编辑</p>
              <h2>{volume.title}</h2>
            </div>
            <span>{values.chapter_range}</span>
          </header>

          <div className="outline-beat-editor-layout">
            <aside className="outline-beat-editor-nav" aria-label="大纲编辑对象">
              <button aria-pressed={focusKey === 'overview'} className={focusKey === 'overview' ? 'active overview' : 'overview'} onClick={() => setFocusKey('overview')} type="button">
                <small>卷</small><b>总览</b>
                <span>{values.volume_goal || '卷目标 / 节奏曲线'}</span>
              </button>
              {OUTLINE_BEAT_DEFINITIONS.map(({ key, label, hint }, index) => (
                <button aria-pressed={focusKey === key} className={focusKey === key ? 'active' : ''} key={key} onClick={() => setFocusKey(key)} type="button">
                  <small>{String(index + 1).padStart(2, '0')}</small>
                  <b>{label}</b>
                  <span>{values[key] || hint}</span>
                </button>
              ))}
            </aside>

            <section className="outline-beat-editor-focus" aria-label="当前编辑内容">
              {focusKey === 'overview' ? (
                <div className="outline-focus-overview">
                  <ArtifactDraftField error={errors.volume_goal} id="outline-volume-goal" label="卷目标" required>
                    {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={values.volume_goal} onChange={(event) => update('volume_goal', event.target.value)} />}
                  </ArtifactDraftField>
                  <ArtifactDraftField error={errors.rhythm} id="outline-volume-rhythm" label="节奏曲线" required>
                    {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={values.rhythm} onChange={(event) => update('rhythm', event.target.value)} />}
                  </ArtifactDraftField>
                </div>
              ) : focusField ? (
                <ArtifactDraftField
                  className={`outline-focus-field ${focusField.tone}`}
                  error={errors[focusField.key]}
                  hint={focusField.hint}
                  id={`outline-beat-${focusField.key}`}
                  label={<strong>{focusField.label}</strong>}
                  required
                >
                  {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={values[focusField.key]} onChange={(event) => update(focusField.key, event.target.value)} />}
                </ArtifactDraftField>
              ) : null}
            </section>
          </div>

          {readOnly ? null : (
            <ArtifactDraftActions
              dirty={dirty}
              invalidCount={invalidCount}
              onClose={requestClose}
              onSave={() => onSave(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.trim()]))) }
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

function volumeValues(volume: OutlineVolume) {
  return {
    chapter_range: volume.chapter_range,
    climax: volume.climax ?? '',
    development: volume.development ?? '',
    midpoint: volume.midpoint ?? volume.mid_twist ?? '',
    opening: volume.opening ?? '',
    resolution: volume.resolution ?? volume.volume_cliffhanger ?? '',
    rhythm: volume.rhythm ?? '',
    volume_goal: volume.volume_goal || volume.goal || '',
  };
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
