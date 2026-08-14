import type { Transition, Variants } from 'motion/react';

type MotionEase = [number, number, number, number];

export const motionDuration = {
  instant: 0,
  feedback: 0.1,
  exit: 0.12,
  fast: 0.16,
  standard: 0.22,
  slow: 0.28,
} as const;

export const motionEase: Record<'standard' | 'emphasized' | 'decelerate', MotionEase> = {
  standard: [0.2, 0.8, 0.2, 1],
  emphasized: [0.18, 0.86, 0.18, 1],
  decelerate: [0.16, 1, 0.3, 1],
};

export const motionTransition = {
  instant: { duration: motionDuration.instant },
  feedback: { duration: motionDuration.feedback, ease: motionEase.standard },
  exit: { duration: motionDuration.exit, ease: motionEase.standard },
  fast: { duration: motionDuration.fast, ease: motionEase.standard },
  standard: { duration: motionDuration.standard, ease: motionEase.standard },
  slow: { duration: motionDuration.slow, ease: motionEase.decelerate },
} satisfies Record<string, Transition>;

export function motionTransitionFor(reducedMotion: boolean, transition: Transition = motionTransition.standard): Transition {
  return reducedMotion ? motionTransition.instant : transition;
}

export const interactionMotionVariants: Variants = {
  rest: { scale: 1 },
  hover: { scale: 1.012, transition: motionTransition.feedback },
  pressed: { scale: 0.98, transition: motionTransition.feedback },
};

export const tabMotionVariants: Variants = {
  inactive: { opacity: 0.72 },
  active: { opacity: 1, transition: motionTransition.fast },
};

export const contentSwapMotionVariants: Variants = {
  initial: { opacity: 0, x: 4 },
  animate: { opacity: 1, x: 0, transition: motionTransition.fast },
  exit: { opacity: 0, x: -4, transition: motionTransition.exit },
};

export const overlayExitDurationMs = {
  dialog: 160,
  sheet: 160,
} as const;

export const backdropMotionVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: motionTransition.fast },
  exit: { opacity: 0, transition: motionTransition.exit },
};

export const dialogMotionVariants: Variants = {
  initial: { opacity: 0, scale: 0.98, y: 8 },
  animate: { opacity: 1, scale: 1, y: 0, transition: motionTransition.standard },
  exit: { opacity: 0, scale: 0.99, y: 4, transition: motionTransition.fast },
};

export const sheetMotionVariants: Variants = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0, transition: motionTransition.standard },
  exit: { opacity: 0, x: 12, transition: motionTransition.fast },
};

export const toastMotionVariants: Variants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: motionTransition.fast },
  exit: { opacity: 0, y: 4, transition: motionTransition.exit },
};

/** Direction-neutral (browser history has no direction); enter reads slower than exit. */
export const routeMotionVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: motionTransition.standard },
  exit: { opacity: 0, transition: motionTransition.exit },
};

export const streamingMotionVariants: Variants = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0, transition: motionTransition.fast },
};
