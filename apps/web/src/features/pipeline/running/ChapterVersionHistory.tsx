import { History, RotateCcw, X } from 'lucide-react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import type { WritingVersion } from './writingArtifactModel';

type Props = {
  busy: boolean;
  currentVersion: number;
  error: string;
  versions: WritingVersion[];
  onClose: () => void;
  onRestore: (versionId: string) => void;
};

export function ChapterVersionHistory({
  busy,
  currentVersion,
  error,
  versions,
  onClose,
  onRestore,
}: Props) {
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  return createPortal(
    <motion.div animate="animate" className="app-overlay-backdrop chapter-version-backdrop" exit="exit" initial="initial" onClick={busy ? undefined : onClose} variants={backdropMotionVariants}>
      <motion.section
        animate="animate"
        aria-busy={busy}
        aria-label="章节版本历史"
        aria-modal="true"
        className="app-dialog-surface chapter-version-dialog"
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <header>
          <div><History size={16} /><span><strong>章节版本</strong><small>当前 v{currentVersion} · 恢复后创建新版本</small></span></div>
          <button aria-label="关闭版本历史" className="modal-close" disabled={busy} onClick={onClose} type="button"><X size={17} /></button>
        </header>
        <div className="chapter-version-list">
          {versions.length ? [...versions].reverse().map((version) => (
            <article key={version.id}>
              <div><strong>v{version.version}</strong><small>{sourceLabel(version.source)} · {version.words.toLocaleString()} 字</small></div>
              <p>{version.content.replace(/\s+/g, ' ').slice(0, 110)}</p>
              <button disabled={busy} onClick={() => onRestore(version.id)} title={`恢复 v${version.version}`} type="button">
                <RotateCcw size={13} /><span>恢复</span>
              </button>
            </article>
          )) : <p className="chapter-version-empty">创建一次局部修订后，这里会保留可恢复的完整章节版本。</p>}
        </div>
        {error ? <p className="chapter-revision-error" role="alert">{error}</p> : null}
      </motion.section>
    </motion.div>,
    document.body,
  );
}

function sourceLabel(source: string) {
  return {
    manual_edit: '人工编辑',
    model_generation: '模型初稿',
    selection_revision: '局部修订',
  }[source] ?? '章节版本';
}
