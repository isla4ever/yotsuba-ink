import { motion } from 'motion/react';
import { useEffect, useState, type ReactNode } from 'react';
import { motionTransition, motionTransitionFor } from '../lib/motion';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';

type Props = {
  children: ReactNode;
  className?: string;
  open: boolean;
};

export function StageFinalizeTray({ children, className = '', open }: Props) {
  const reducedMotion = useReducedMotionPreference();
  const [rendered, setRendered] = useState(open);
  const [collapsed, setCollapsed] = useState(!open);

  useEffect(() => {
    if (!open) return;
    setRendered(true);
    setCollapsed(false);
  }, [open]);

  return (
    <motion.div
      animate={{ opacity: open ? 1 : 0, y: open ? 0 : 8 }}
      aria-hidden={!open}
      className={`stage-finalize-tray ${className}${collapsed ? ' collapsed' : ''}`.trim()}
      initial={false}
      onAnimationComplete={() => {
        if (!open) {
          setCollapsed(true);
          setRendered(false);
        }
      }}
      transition={motionTransitionFor(reducedMotion, open ? motionTransition.standard : motionTransition.exit)}
    >
      <div className="stage-finalize-tray-inner">{rendered ? children : null}</div>
    </motion.div>
  );
}
