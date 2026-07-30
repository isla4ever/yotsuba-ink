import { AnimatePresence, motion } from 'motion/react';
import { BookOpen, Clock3, Compass, PanelLeft, PlayCircle, Settings, X, type LucideIcon } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';
import { motionDuration, motionTransitionFor, overlayExitDurationMs, sheetMotionVariants } from '../lib/motion';
import type { QualityMode } from '../contracts';
import { creationModeTitle } from '../lib/terminology';

export type ProductNavigationItemId = 'planning' | 'running' | 'knowledge' | 'history' | 'settings';

export type ProductNavigationItem = {
  id: ProductNavigationItemId;
  label: string;
  description: string;
  icon: LucideIcon;
  disabled?: boolean;
  disabledReason?: string;
  badge?: string;
};

type Props = {
  open: boolean;
  activeItem: ProductNavigationItemId;
  items: ProductNavigationItem[];
  qualityMode: QualityMode;
  onOpenChange: (open: boolean) => void;
  onNavigate: (item: ProductNavigationItem) => void;
};

export const productNavigationIcons = {
  planning: Compass,
  running: PlayCircle,
  knowledge: BookOpen,
  history: Clock3,
  settings: Settings,
} satisfies Record<ProductNavigationItemId, LucideIcon>;

export function ProductNavigationRail({ open, activeItem, items, qualityMode, onOpenChange, onNavigate }: Props) {
  const reducedMotion = useReducedMotionPreference();
  const panelRef = useOverlayDialog<HTMLElement>({
    exitDurationMs: overlayExitDurationMs.sheet,
    onClose: () => onOpenChange(false),
    open,
  });

  return (
    <>
      <button
        aria-controls="product-navigation-rail"
        aria-expanded={open}
        aria-label={open ? '关闭产品导航' : '打开产品导航'}
        className={`product-navigation-trigger ${open ? 'active' : ''}`}
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        {open ? <X size={17} /> : <PanelLeft size={17} />}
      </button>
      {createPortal(
        <AnimatePresence initial={false}>
          {open ? (
            <div className={`product-navigation-layer mode-${qualityMode}`}>
              <motion.button
                aria-label="关闭产品导航"
                className="product-navigation-backdrop"
                exit={{ opacity: 0, transition: motionTransitionFor(reducedMotion, { duration: motionDuration.exit }) }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1, transition: motionTransitionFor(reducedMotion) }}
                onClick={() => onOpenChange(false)}
                type="button"
              />
              <motion.aside
                aria-label="产品导航"
                aria-modal="true"
                className="product-navigation-rail"
                exit={{ opacity: 0, x: -16, transition: motionTransitionFor(reducedMotion, { duration: motionDuration.exit }) }}
                id="product-navigation-rail"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0, transition: motionTransitionFor(reducedMotion, { duration: motionDuration.standard }) }}
                ref={panelRef}
                role="dialog"
                tabIndex={-1}
              >
                <header className="product-navigation-head">
                  <div>
                    <span className="eyebrow">Yotsuba Ink</span>
                    <strong>工作台导航</strong>
                  </div>
                  <button aria-label="关闭产品导航" className="icon-button" onClick={() => onOpenChange(false)} type="button"><X size={16} /></button>
                </header>
                <nav aria-label="产品入口" className="product-navigation-list">
                  {items.map((item, index) => {
                    const Icon = item.icon;
                    const active = item.id === activeItem;
                    return (
                      <motion.button
                        animate={{ opacity: 1, x: 0 }}
                        className={`product-navigation-item ${active ? 'active' : ''}`}
                        disabled={item.disabled}
                        initial={reducedMotion ? false : { opacity: 0, x: -8 }}
                        key={item.id}
                        onClick={() => onNavigate(item)}
                        title={item.disabled ? item.disabledReason : item.description}
                        transition={motionTransitionFor(reducedMotion, { duration: motionDuration.fast, delay: index * 0.025 })}
                        type="button"
                      >
                        <span className="product-navigation-item-icon"><Icon size={17} /></span>
                        <span className="product-navigation-item-copy"><strong>{item.label}</strong><small>{item.disabled ? item.disabledReason : item.description}</small></span>
                        {item.badge ? <span className="product-navigation-item-badge">{item.badge}</span> : null}
                      </motion.button>
                    );
                  })}
                </nav>
                <footer className="product-navigation-foot">当前模式：{qualityModeLabel(qualityMode)} · 入口切换不会重新生成内容</footer>
              </motion.aside>
            </div>
          ) : null}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}

function qualityModeLabel(mode: QualityMode) {
  return creationModeTitle(mode);
}
