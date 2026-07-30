import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';

type Props = {
  children: ReactNode;
  className?: string;
  open: boolean;
};

export function LiquidGlassOverlay({ children, className = '', open }: Props) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className={`liquid-glass-overlay ${className}`.trim()}
          exit="exit"
          initial="initial"
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            className="liquid-glass-card"
            exit="exit"
            initial="initial"
            variants={dialogMotionVariants}
          >
            {children}
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
