import { MotionConfig } from 'motion/react';
import type { ReactNode } from 'react';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';

type Props = {
  children: ReactNode;
};

export function MotionPreferenceProvider({ children }: Props) {
  const reducedMotion = useReducedMotionPreference();
  return (
    <MotionConfig reducedMotion="never" skipAnimations={reducedMotion}>
      {children}
    </MotionConfig>
  );
}
