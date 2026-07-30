import { CircleAlert, Save, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useLayoutEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import type { DetailBaseline } from './detailArtifactModel';
import { validateDetailBlueprintDraft, type DetailBlueprintDraft } from './detailDraftValidation';
import { focusFirstDetailError } from './detailValidationFocus';
import { ChapterBlueprintPaper } from './ChapterBlueprintPaper';
import type { DetailOutlineArtifact } from './stageArtifacts';

type Chapter = DetailOutlineArtifact['chapters'][number];
export type ChapterBlueprintValues = DetailBlueprintDraft;

type Props = {
  baseline: DetailBaseline;
  chapter: Chapter;
  chapterIndex: number;
  chapters: Chapter[];
  onChapterChange: (chapterIndex: number) => void;
  onClose: () => void;
  onSave: (values: ChapterBlueprintValues) => void;
  readOnly?: boolean;
};

export function ChapterBlueprintDialog({ baseline, chapter, chapterIndex, chapters, onChapterChange, onClose, onSave, readOnly = false }: Props) {
  const defaults = useMemo(() => chapterValues(chapter), [chapter]);
  const [draft, setDraft] = useState(() => ({ chapterIndex, initialValues: defaults, values: defaults }));
  const [validationAttempted, setValidationAttempted] = useState(false);
  const activeDraft = draft.chapterIndex === chapterIndex
    ? draft
    : { chapterIndex, initialValues: defaults, values: defaults };
  const { initialValues, values } = activeDraft;
  useLayoutEffect(() => {
    setDraft((current) => current.chapterIndex === chapterIndex
      ? current
      : { chapterIndex, initialValues: defaults, values: defaults });
    setValidationAttempted(false);
  }, [chapterIndex, defaults]);
  const validation = useMemo(
    () => validateDetailBlueprintDraft(values, baseline, chapters.map((item) => item.chapter), chapterIndex),
    [baseline, chapterIndex, chapters, values],
  );
  const errors = validationAttempted ? validation.errors : {};
  const dirty = !draftsEqual(initialValues, values);
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel: '章节蓝图当前稿' });
  const modeClass = usePortalModeClass();
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel: '章节蓝图当前稿' }, onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });
  const update = (key: keyof ChapterBlueprintValues, value: string) => setDraft((current) => {
    const source = current.chapterIndex === chapterIndex ? current : activeDraft;
    return { ...source, values: { ...source.values, [key]: value } };
  });
  const requestChapterChange = (nextIndex: number) => {
    if (nextIndex === chapterIndex) return;
    const destinationLabel = chapters[nextIndex]?.chapter || `第 ${nextIndex + 1} 章`;
    draftGuard.requestAction({ destinationLabel, kind: 'switch', scopeLabel: '当前章节蓝图' }, () => onChapterChange(nextIndex));
  };
  const save = () => {
    setValidationAttempted(true);
    if (!validation.valid) {
      focusFirstDetailError(validation.errors);
      return;
    }
    onSave(validation.value);
  };

  return (
    <>
      {createPortal(
        <AnimatePresence>
      <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
        <motion.section
          animate="animate"
          aria-label={`${chapter.chapter} 章节蓝图`}
          aria-modal="true"
          className={`chapter-blueprint-dialog app-dialog-surface${readOnly ? ' readonly' : ''}`}
          exit="exit"
          initial="initial"
          onClick={(event) => event.stopPropagation()}
          ref={dialogRef}
          role="dialog"
          tabIndex={-1}
          variants={dialogMotionVariants}
        >
          <button aria-label="关闭章节蓝图" className="modal-close" onClick={requestClose} type="button"><X size={21} /></button>
          <header className="chapter-blueprint-head">
            <div><p className="eyebrow">章节结构</p><h2>{chapter.chapter} · 施工蓝图</h2></div>
            <span>{values.pov || 'POV 待补齐'} / {values.scene || '场景待补齐'}</span>
          </header>
          <div className="chapter-blueprint-body">
            <aside className="chapter-blueprint-rail chapter-switch-rail" aria-label="切换章节蓝图">
              {chapters.map((item, index) => (
                <button aria-pressed={index === chapterIndex} className={index === chapterIndex ? 'active' : ''} key={`${item.chapter}-${index}`} onClick={() => requestChapterChange(index)} type="button">
                  <b>{item.chapter}</b><span>{item.pov || 'POV 待补齐'} · {item.scene || '场景待补齐'}</span><small>{item.goal || '目标待补齐'}</small>
                </button>
              ))}
            </aside>
            <div className="chapter-blueprint-paper-viewport">
              <AnimatePresence initial={false} mode="sync">
                <ChapterBlueprintPaper
                  baseline={baseline}
                  errors={errors}
                  key={`${chapterIndex}-${chapter.chapter}`}
                  onChange={update}
                  readOnly={readOnly}
                  validationAttempted={validationAttempted && !validation.valid}
                  values={values}
                />
              </AnimatePresence>
            </div>
          </div>
          {readOnly ? null : (
            <footer className="artifact-dialog-actions chapter-blueprint-actions">
              {validationAttempted && !validation.valid
                ? <span className="detail-validation-status" role="alert"><CircleAlert size={14} />请先修正蓝图内容</span>
                : dirty ? <span className="unsaved-draft-status" role="status"><CircleAlert size={14} />未保存修改</span> : null}
              <button className="ghost tiny-action" onClick={requestClose} type="button">取消</button>
              <button className="mode-primary-action" onClick={save} type="button"><Save size={14} />保存到当前稿</button>
            </footer>
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

function chapterValues(chapter: Chapter): ChapterBlueprintValues {
  return {
    chapter: chapter.chapter,
    pov: chapter.pov,
    scene: chapter.scene,
    goal: chapter.goal,
    entry_state: chapter.entry_state,
    conflict: chapter.conflict,
    stakes: chapter.stakes,
    hook: chapter.hook,
    continuity_notes: chapter.continuity_notes,
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
