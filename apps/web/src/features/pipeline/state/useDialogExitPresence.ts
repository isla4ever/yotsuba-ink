import { useEffect, useState } from 'react';
import { overlayExitDurationMs } from '../lib/motion';
import { useReducedMotionPreference } from './useReducedMotionPreference';

export function useDialogExitPresence(open: boolean) {
  const reducedMotion = useReducedMotionPreference();
  const [presentOpen, setPresentOpen] = useState(open);

  useEffect(() => {
    if (open) {
      setPresentOpen(true);
      return;
    }
    if (!presentOpen) return;

    const timer = window.setTimeout(
      () => setPresentOpen(false),
      reducedMotion ? 0 : overlayExitDurationMs.dialog,
    );
    return () => window.clearTimeout(timer);
  }, [open, presentOpen, reducedMotion]);

  return {
    exiting: presentOpen && !open,
    presentOpen,
  };
}
