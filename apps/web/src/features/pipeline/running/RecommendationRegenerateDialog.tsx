import { RefreshCw, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { backdropMotionVariants, dialogMotionVariants, overlayExitDurationMs } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: (direction: string) => void;
};

const suggestions = [
  '强化悬疑钩子：让开篇问题更尖锐，增强读者追读冲动。',
  '增强人物关系：让主角、关键盟友和隐瞒者之间的张力更清楚。',
  '降低设定复杂度：减少解释负担，把设定转成可行动的线索。',
];

export function RecommendationRegenerateDialog({ open, onClose, onConfirm }: Props) {
  const [direction, setDirection] = useState(suggestions[0]);
  const dialogRef = useOverlayDialog<HTMLElement>({ exitDurationMs: overlayExitDurationMs.dialog, onClose, open });
  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className="recommendation-dialog-backdrop app-overlay-backdrop"
          exit="exit"
          initial="initial"
          role="presentation"
          onClick={onClose}
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            className="recommendation-dialog app-dialog-surface"
            exit="exit"
            initial="initial"
            role="dialog"
            aria-modal="true"
            aria-label="调整创作立项"
            onClick={(event) => event.stopPropagation()}
            ref={dialogRef}
            tabIndex={-1}
            variants={dialogMotionVariants}
          >
            <button aria-label="关闭换一稿弹窗" className="modal-close" onClick={onClose} title="关闭" type="button"><X size={22} /></button>
            <p className="eyebrow">调整方向</p>
            <h2>换一稿</h2>
            <p>选择本次调整重点，也可以直接填写自定义方向。</p>
            <div className="recommendation-suggestion-list">
              {suggestions.map((item) => (
                <button className={direction === item ? 'active' : ''} key={item} onClick={() => setDirection(item)} type="button">{item}</button>
              ))}
            </div>
            <label className="recommendation-direction-field">
              <span>自定义调整方向</span>
              <textarea value={direction} onChange={(event) => setDirection(event.target.value)} />
            </label>
            <div className="recommendation-dialog-actions">
              <button className="ghost tiny-action" onClick={onClose} type="button">取消</button>
              <button className="tech-button" disabled={!direction.trim()} onClick={() => onConfirm(direction.trim())} type="button"><RefreshCw size={14} />按此方向换一稿</button>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
