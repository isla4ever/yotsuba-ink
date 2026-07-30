import { CircleAlert, Save, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import type { CoverArtifact } from './stageArtifacts';

type CoverBriefDraft = Pick<CoverArtifact, 'brief' | 'composition' | 'copy_suggestions' | 'prompt'>;

type Props = {
  artifact: CoverArtifact;
  onClose: () => void;
  onSave: (draft: CoverBriefDraft) => void;
  readOnly: boolean;
};

export function CoverBriefDialog({ artifact, onClose, onSave, readOnly }: Props) {
  const [initialDraft] = useState<CoverBriefDraft>(() => briefDraft(artifact));
  const [draft, setDraft] = useState<CoverBriefDraft>(() => briefDraft(artifact));
  const dirty = !draftsEqual(initialDraft, draft);
  const scopeLabel = '封面生成简报';
  const guard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => guard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(guard.intent) });
  const modeClass = portalModeClass();

  return (
    <>
      {createPortal(
        <AnimatePresence>
          <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
            <motion.section
              animate="animate"
              aria-label="封面生成简报"
              aria-modal="true"
              className={`cover-brief-dialog app-dialog-surface${readOnly ? ' readonly' : ''}`}
              exit="exit"
              initial="initial"
              onClick={(event) => event.stopPropagation()}
              ref={dialogRef}
              role="dialog"
              tabIndex={-1}
              variants={dialogMotionVariants}
            >
              <button aria-label="关闭封面生成简报" className="modal-close" onClick={requestClose} type="button"><X size={20} /></button>
              <header><p className="eyebrow">封面创作输入</p><h2>封面生成简报</h2><span>简报与提示词只影响后续换一稿，不替代正式图片资产。</span></header>
              <div className="cover-brief-editor">
                <label><span>封面目标</span><textarea readOnly={readOnly} value={draft.brief} onChange={(event) => setDraft((current) => ({ ...current, brief: event.target.value }))} /></label>
                <label><span>构图说明</span><textarea readOnly={readOnly} value={draft.composition} onChange={(event) => setDraft((current) => ({ ...current, composition: event.target.value }))} /></label>
                <label><span>封面文案</span><input readOnly={readOnly} value={draft.copy_suggestions[0] || ''} onChange={(event) => setDraft((current) => ({ ...current, copy_suggestions: [event.target.value, ...current.copy_suggestions.slice(1)] }))} /></label>
                <label className="prompt"><span>图片提示词</span><textarea readOnly={readOnly} value={draft.prompt} onChange={(event) => setDraft((current) => ({ ...current, prompt: event.target.value }))} /></label>
              </div>
              {readOnly ? null : (
                <footer className="artifact-dialog-actions">
                  {dirty ? <span className="unsaved-draft-status" role="status"><CircleAlert size={14} />未保存修改</span> : null}
                  <button className="ghost tiny-action" onClick={requestClose} type="button">取消</button>
                  <button className="mode-primary-action" disabled={!draft.brief.trim() || !draft.composition.trim() || !draft.prompt.trim()} onClick={() => onSave(draft)} type="button"><Save size={14} />保存到当前稿</button>
                </footer>
              )}
            </motion.section>
          </motion.div>
        </AnimatePresence>,
        document.body,
      )}
      {guard.intent ? <UnsavedDraftDialog intent={guard.intent} modeClass={modeClass} onCancel={guard.cancelDiscard} onDiscard={guard.confirmDiscard} /> : null}
    </>
  );
}

function briefDraft(artifact: CoverArtifact): CoverBriefDraft {
  return {
    brief: artifact.brief,
    composition: artifact.composition,
    copy_suggestions: [...artifact.copy_suggestions],
    prompt: artifact.prompt,
  };
}

function portalModeClass() {
  if (typeof document === 'undefined') return '';
  const shell = document.querySelector('.product-shell');
  return ['mode-fast', 'mode-balanced', 'mode-deep'].find((name) => shell?.classList.contains(name)) ?? '';
}
