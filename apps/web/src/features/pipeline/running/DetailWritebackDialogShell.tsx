import { CircleAlert, Save, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import type { DetailBaseline } from './detailArtifactModel';
import type { DetailOutlineArtifact } from './stageArtifacts';

export type DetailChapter = DetailOutlineArtifact['chapters'][number];

export type DetailWritebackDialogBaseProps = {
  baseline: DetailBaseline;
  chapter: DetailChapter;
  chapterIndex: number;
  chapters: DetailChapter[];
  onChapterChange: (chapterIndex: number) => void;
  onClose: () => void;
  readOnly?: boolean;
};

type DraftGuard = ReturnType<typeof useUnsavedDraftGuard>;

export function DetailWritebackDialogShell({
  chapter,
  chapterIndex,
  chapters,
  children,
  dirty,
  draftGuard,
  icon,
  kicker,
  onChapterChange,
  onClose,
  onSave,
  readOnly = false,
  scopeLabel,
  title,
  validationErrorCount = 0,
}: {
  chapter: DetailChapter;
  chapterIndex: number;
  chapters: DetailChapter[];
  children: ReactNode;
  dirty: boolean;
  draftGuard: DraftGuard;
  icon: ReactNode;
  kicker: string;
  onChapterChange: (chapterIndex: number) => void;
  onClose: () => void;
  onSave: () => void;
  readOnly?: boolean;
  scopeLabel: string;
  title: string;
  validationErrorCount?: number;
}) {
  const modeClass = usePortalModeClass();
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const requestChapterChange = (nextIndex: number) => {
    if (nextIndex === chapterIndex) return;
    const destinationLabel = chapters[nextIndex]?.chapter || `第 ${nextIndex + 1} 章`;
    draftGuard.requestAction({ destinationLabel, kind: 'switch', scopeLabel }, () => onChapterChange(nextIndex));
  };
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });

  return (
    <>
      {createPortal(
        <AnimatePresence>
          <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
            <motion.section
              animate="animate"
              aria-label={`${chapter.chapter} ${title}`}
              aria-modal="true"
              className={`detail-writeback-dialog app-dialog-surface${readOnly ? ' readonly' : ''}`}
              exit="exit"
              initial="initial"
              onClick={(event) => event.stopPropagation()}
              ref={dialogRef}
              role="dialog"
              tabIndex={-1}
              variants={dialogMotionVariants}
            >
              <button aria-label={`关闭${title}`} className="modal-close" onClick={requestClose} type="button"><X size={21} /></button>
              <header className="detail-writeback-head">
                <div><p className="eyebrow">{kicker}</p><h2>{icon}{chapter.chapter} · {title}</h2></div>
                <span>{chapter.pov || 'POV 待补齐'} / {chapter.scene || '场景待补齐'}</span>
              </header>
              <div className="detail-writeback-body">
                <aside className="detail-writeback-chapter-rail" aria-label={`切换章节${title}`}>
                  {chapters.map((item, index) => (
                    <button aria-pressed={index === chapterIndex} className={index === chapterIndex ? 'active' : ''} key={`${item.chapter}-${index}`} onClick={() => requestChapterChange(index)} type="button">
                      <b>{item.chapter.replace('第', '').replace('章', '')}</b><span>{item.chapter}</span><small>{item.scene || item.pov || '章节上下文'}</small>
                    </button>
                  ))}
                </aside>
                <section className="detail-writeback-panel">{children}</section>
              </div>
              {readOnly ? null : (
                <footer className="artifact-dialog-actions detail-writeback-actions">
                  {validationErrorCount > 0
                    ? <span className="detail-validation-status" role="alert"><CircleAlert size={14} />还有 {validationErrorCount} 处需要修正</span>
                    : dirty ? <span className="unsaved-draft-status" role="status"><CircleAlert size={14} />未保存修改</span> : null}
                  <button className="ghost tiny-action" onClick={requestClose} type="button">取消</button>
                  <button className="mode-primary-action" onClick={onSave} type="button"><Save size={14} />保存到当前稿</button>
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
