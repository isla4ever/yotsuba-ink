import { motion } from 'motion/react';
import { Cpu, FileKey2, ShieldCheck, Timer, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import type { GraphRunDefinition, WorkflowDefinition } from '../contracts';
import { backdropMotionVariants, sheetMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { frozenBindingInventory } from './frozenBindingInventory';

type Props = {
  definition: GraphRunDefinition;
  workflow: WorkflowDefinition;
  onClose: () => void;
};

export function FrozenBindingInventorySheet({ definition, workflow, onClose }: Props) {
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  const items = frozenBindingInventory(definition, workflow);
  return createPortal(
    <motion.div
      animate="animate"
      className={`runtime-side-detail-backdrop app-overlay-backdrop mode-${definition.quality_mode}`}
      exit="exit"
      initial="initial"
      onClick={onClose}
      variants={backdropMotionVariants}
    >
      <motion.aside
        animate="animate"
        aria-label="冻结 Provider 绑定"
        aria-modal="true"
        className={`runtime-side-detail-sheet frozen-binding-sheet mode-${definition.quality_mode}`}
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={sheetMotionVariants}
      >
        <header className="runtime-side-detail-head">
          <div>
            <p className="eyebrow">Run Definition · 只读</p>
            <h2>冻结 Provider 绑定</h2>
          </div>
          <button aria-label="关闭冻结配置" className="modal-close" onClick={onClose} type="button"><X size={20} /></button>
        </header>
        <div className="frozen-binding-body">
          <div className="frozen-binding-summary">
            <ShieldCheck aria-hidden="true" size={18} />
            <p><strong>{workflow.name}</strong><span>{definition.workflow_revision} · {definition.quality_mode}</span></p>
          </div>
          <ol className="frozen-binding-list">
            {items.map((item) => (
              <li key={item.id}>
                <header><span>{item.stageLabel}</span><code>{item.id}</code></header>
                <dl>
                  <div><dt><Cpu size={14} />Provider / 模型</dt><dd>{item.provider}<strong>{item.model}</strong></dd></div>
                  <div><dt><FileKey2 size={14} />Prompt 身份</dt><dd>{item.prompt}</dd></div>
                  <div><dt><Timer size={14} />生成预算</dt><dd>{item.budget}</dd></div>
                  <div><dt>审稿</dt><dd>{item.review}</dd></div>
                  <div><dt>写回</dt><dd>{item.writeback}</dd></div>
                </dl>
              </li>
            ))}
          </ol>
        </div>
      </motion.aside>
    </motion.div>,
    document.body,
  );
}
