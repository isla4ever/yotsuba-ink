import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, type ReactNode } from 'react';
import { motionDuration, routeMotionVariants } from '../lib/motion';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';

type Props = {
  children: ReactNode;
  label: string;
  routeKey: string;
};

export function WorkbenchRouteTransition({ children, label, routeKey }: Props) {
  const activeSurfaceRef = useRef<HTMLDivElement | null>(null);
  const previousRouteKeyRef = useRef(routeKey);
  const reducedMotion = useReducedMotionPreference();

  useEffect(() => {
    if (previousRouteKeyRef.current === routeKey) return;
    previousRouteKeyRef.current = routeKey;
    const timer = window.setTimeout(
      () => activeSurfaceRef.current?.focus({ preventScroll: true }),
      reducedMotion ? 0 : motionDuration.fast * 1000,
    );
    return () => window.clearTimeout(timer);
  }, [reducedMotion, routeKey]);

  return (
    <div className="workspace-route-transition">
      <AnimatePresence initial={false} mode="sync">
        <motion.div
          animate="animate"
          className="workspace-route-surface"
          exit="exit"
          initial="initial"
          key={routeKey}
          variants={routeMotionVariants}
        >
          <div
            aria-label={label}
            className="workspace-route-focus-region"
            data-route-key={routeKey}
            ref={(node) => {
              if (node) activeSurfaceRef.current = node;
              else if (activeSurfaceRef.current?.dataset.routeKey === routeKey) activeSurfaceRef.current = null;
            }}
            role="region"
            tabIndex={-1}
          >
            {children}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
