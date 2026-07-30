import { RotateCcw, Undo2, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { QualityMode } from '../contracts';
import { toastMotionVariants } from '../lib/motion';
import { ControlTooltip } from './ControlTooltip';
import { DangerConfirmationDialog } from './DangerConfirmationDialog';
import { LoadingButton } from './LoadingButton';

type Props = {
  canReset: boolean;
  canUndoReset: boolean;
  mode: QualityMode;
  onDismissUndo: () => void;
  onReset: () => boolean;
  onUndo: () => Promise<void>;
  runId: string;
  undoAvailable: boolean;
};

export function RunResetControl({ canReset, canUndoReset, mode, onDismissUndo, onReset, onUndo, runId, undoAvailable }: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const tooltip = canReset ? '重置当前运行' : '当前没有可重置的运行';

  const confirmReset = () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    const reset = onReset();
    if (reset) setDialogOpen(false);
    busyRef.current = false;
    setBusy(false);
  };

  const undoReset = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await onUndo();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <>
      <ControlTooltip label={tooltip}>
        <button
          aria-label="重置当前运行"
          className="icon-button tech-icon-button run-reset-button"
          disabled={!canReset || busy}
          onClick={() => setDialogOpen(true)}
          type="button"
        >
          <RotateCcw size={15} />
        </button>
      </ControlTooltip>
      <DangerConfirmationDialog
        busy={busy}
        busyLabel="正在重置"
        confirmLabel="重置并返回工作台"
        description="这会停止当前页面的实时进度，并清除本机保存的进度记录和确认点。"
        details={[
          `当前运行：${runId}`,
          '创作历史、交付版本、工作流配置、创作模式和知识库均会保留。',
          canUndoReset
            ? '重置后可在 15 秒内撤销；撤销只恢复为暂停状态，不会自动继续创作。'
            : '这次运行还没有可恢复的记录，重置后无法撤销。',
        ]}
        modeClass={`mode-${mode}`}
        onCancel={() => setDialogOpen(false)}
        onConfirm={confirmReset}
        open={dialogOpen}
        title="重置当前运行界面？"
      />
      {createPortal(
        <AnimatePresence>
          {undoAvailable ? (
            <motion.aside
              animate="animate"
              aria-busy={busy}
              aria-live="polite"
              className={`run-reset-undo-notice mode-${mode}`}
              exit="exit"
              initial="initial"
              role="status"
              variants={toastMotionVariants}
            >
              <RotateCcw aria-hidden="true" size={17} />
              <div><strong>运行入口已重置</strong><span>历史、配置和知识库仍保留。</span></div>
              <LoadingButton className="run-reset-undo-action" loading={busy} loadingLabel="撤销中" onClick={() => void undoReset()}><Undo2 size={14} />撤销</LoadingButton>
              <button aria-label="关闭重置提示" className="run-reset-dismiss" disabled={busy} onClick={onDismissUndo} type="button"><X size={14} /></button>
            </motion.aside>
          ) : null}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}
