import { CheckCircle2 } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef } from 'react';
import { toastMotionVariants } from '../lib/motion';

export function StageToast({ durationMs = 1800, message, onDismiss }: { durationMs?: number; message: string; onDismiss: () => void }) {
  const onDismissRef = useRef(onDismiss);
  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => onDismissRef.current(), durationMs);
    return () => window.clearTimeout(timer);
  }, [durationMs, message]);

  return (
    <AnimatePresence mode="sync">
      {message ? (
        <motion.div animate="animate" className="stage-toast" exit="exit" initial="initial" key={message} variants={toastMotionVariants}>
          <CheckCircle2 size={14} />{message}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
