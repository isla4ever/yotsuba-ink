import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { ManuscriptLoadingIndicator } from './ManuscriptLoadingIndicator';

type Props = {
  children?: ReactNode;
  className?: string;
  contained?: boolean;
  detail?: string;
  eyebrow?: string;
  open?: boolean;
  title: string;
};

export function LoadingOverlay({
  children,
  className = '',
  contained = false,
  detail,
  eyebrow = '创作引擎',
  open = true,
  title,
}: Props) {
  return (
    <AnimatePresence initial={false}>
      {open ? (
        <motion.div
          animate="animate"
          aria-busy="true"
          className={`nw-loading-overlay${contained ? ' is-contained' : ''}${className ? ` ${className}` : ''}`}
          exit="exit"
          initial="initial"
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            aria-live="polite"
            className="nw-loading-overlay-content"
            exit="exit"
            initial="initial"
            role="status"
            variants={dialogMotionVariants}
          >
            <ManuscriptLoadingIndicator />
            <div className="nw-loading-overlay-copy">
              <p className="eyebrow">{eyebrow}</p>
              <h2>{title}</h2>
              {detail ? <p>{detail}</p> : null}
            </div>
            {children ? <div className="nw-loading-overlay-detail">{children}</div> : null}
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
