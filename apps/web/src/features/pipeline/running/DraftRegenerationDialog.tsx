import { RefreshCw, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import type { QualityMode, WorkflowStage } from '../contracts';
import { backdropMotionVariants, dialogMotionVariants, overlayExitDurationMs } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { ArtifactDraftField } from './ArtifactDraftField';
import { regenerationSuggestionsForStage, resolveRegenerationDirection } from './draftRegenerationModel';

type Props = {
  mode: QualityMode;
  onClose: () => void;
  onConfirm: (direction: string) => void;
  open: boolean;
  stage?: WorkflowStage;
};

export function DraftRegenerationDialog({ mode, onClose, onConfirm, open, stage }: Props) {
  const suggestions = regenerationSuggestionsForStage(stage);
  const [selectedSuggestion, setSelectedSuggestion] = useState(suggestions[0]);
  const [customDirection, setCustomDirection] = useState('');
  const direction = resolveRegenerationDirection(selectedSuggestion, customDirection);
  const dialogRef = useOverlayDialog<HTMLElement>({ exitDurationMs: overlayExitDurationMs.dialog, onClose, open });

  useEffect(() => {
    if (open) {
      setSelectedSuggestion(suggestions[0]);
      setCustomDirection('');
    }
  }, [open, stage?.id]);

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className={`recommendation-dialog-backdrop app-overlay-backdrop mode-${mode}`}
          exit="exit"
          initial="initial"
          onClick={onClose}
          role="presentation"
          variants={backdropMotionVariants}
          >
          <motion.section
            animate="animate"
            aria-label={`${stage?.label ?? '小说信息推荐'}换一稿`}
            aria-modal="true"
            className={`recommendation-dialog app-dialog-surface draft-regeneration-dialog mode-${mode}`}
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            ref={dialogRef}
            tabIndex={-1}
            variants={dialogMotionVariants}
          >
            <button aria-label="关闭换一稿弹窗" className="modal-close" onClick={onClose} title="关闭" type="button"><X size={22} /></button>
            <p className="eyebrow">调整方向</p>
            <h2>{stage?.label ? `${stage.label}换一稿` : '换一稿'}</h2>
            <p>{stage?.label ? '选择一个阶段相关调整方向，系统会生成最多 3 个候选稿，用户手动选择当前稿。' : '选择新版推荐的调整方向，系统会更新书名、简介、世界观和人物关系。'}</p>
            <div aria-label="换一稿调整方向" className="recommendation-suggestion-list draft-direction-options" role="radiogroup">
              {suggestions.map((item, index) => (
                <label className={selectedSuggestion === item ? 'active' : ''} key={item}>
                  <input
                    checked={selectedSuggestion === item}
                    name="draft-regeneration-direction"
                    onChange={() => {
                      setSelectedSuggestion(item);
                      setCustomDirection('');
                    }}
                    type="radio"
                    value={item}
                  />
                  <span><small>方向 {String(index + 1).padStart(2, '0')}</small>{item}</span>
                </label>
              ))}
            </div>
            <ArtifactDraftField className={`recommendation-direction-field${!selectedSuggestion ? ' active' : ''}`} id="draft-custom-direction" label="自定义调整方向">
              {(controlProps) => (
                <textarea
                  {...controlProps}
                  placeholder="输入你希望这一稿重点改变的内容"
                  value={customDirection}
                  onChange={(event) => {
                    setCustomDirection(event.target.value);
                    setSelectedSuggestion('');
                  }}
                  onFocus={() => setSelectedSuggestion('')}
                />
              )}
            </ArtifactDraftField>
            <div className="recommendation-dialog-actions">
              <button className="ghost tiny-action" onClick={onClose} type="button">取消</button>
              <button
                className="mode-primary-action"
                disabled={!direction}
                onClick={() => onConfirm(direction)}
                type="button"
              >
                <RefreshCw size={14} />按此方向换一稿
              </button>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
