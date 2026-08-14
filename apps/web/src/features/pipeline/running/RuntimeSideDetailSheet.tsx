import { motion } from 'motion/react';
import { X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { backdropMotionVariants, sheetMotionVariants } from '../lib/motion';
import { RuntimeInsightPanel, type RuntimeInsightContext } from './RuntimeInsightPanel';
import type { RuntimePanelKey } from './stageRuntimeLayout';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { TERM } from '../lib/terminology';

type Props = RuntimeInsightContext & {
  panel: RuntimePanelKey;
  onClose: () => void;
};

const panelTitles: Record<RuntimePanelKey, string> = {
  character: '人物关系网',
  worldbuilding: '世界观详情',
  quality: TERM.qualityCheck,
  wiki: 'Wiki 事实层',
  knowledge: '知识库',
  contextManifest: '本章 Context Manifest',
  coverQuality: '封面质量',
  exportSummary: '导出摘要',
};

export function RuntimeSideDetailSheet({ panel, onClose, ...context }: Props) {
  const title = panelTitles[panel];
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  return createPortal(
    <motion.div
      animate="animate"
      className={`runtime-side-detail-backdrop app-overlay-backdrop mode-${context.workflow.quality_mode}`}
      exit="exit"
      initial="initial"
      onClick={onClose}
      variants={backdropMotionVariants}
    >
      <motion.aside
        animate="animate"
        aria-label={title}
        aria-modal="true"
        className={`runtime-side-detail-sheet app-sheet-surface panel-${panel} mode-${context.workflow.quality_mode}`}
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        ref={dialogRef}
        tabIndex={-1}
        variants={sheetMotionVariants}
      >
        <header className="runtime-side-detail-head">
          <div>
            <p className="eyebrow">运行详情</p>
            <h2>{title}</h2>
          </div>
          <button aria-label="关闭详情" className="modal-close" onClick={onClose} type="button"><X size={20} /></button>
        </header>
        <div className="runtime-side-detail-body">
          <RuntimeInsightPanel {...context} detail panel={panel} />
        </div>
      </motion.aside>
    </motion.div>,
    document.body,
  );
}
