import { useEffect, useState } from 'react';
import {
  nextRevealLength,
  shouldCompleteStreamReveal,
  streamRevealPace,
  type StreamRevealMode,
  type StreamRevealPace,
} from '../lib/streamText';
import { useReducedMotionPreference } from './useReducedMotionPreference';

type StreamRevealOptions = {
  active: boolean;
  mode?: StreamRevealMode;
  tickMs?: number;
};

export type StreamReveal = {
  /** backlog 加速档位：渲染层据此切换新词入场变体（fade / blur）。 */
  pace: StreamRevealPace;
  text: string;
};

export function useStreamReveal(target: string, { active, mode = 'prose', tickMs = 42 }: StreamRevealOptions): StreamReveal {
  const [visible, setVisible] = useState(target);
  const reducedMotion = useReducedMotionPreference();
  const documentHidden = useDocumentHidden();

  useEffect(() => {
    setVisible((current) => {
      const normalized = target.startsWith(current) ? current : '';
      const complete = shouldCompleteStreamReveal({
        active,
        backlog: target.length - normalized.length,
        documentHidden,
        reducedMotion,
      });
      if (complete) return target;
      return normalized.length > target.length ? target : normalized;
    });
  }, [active, documentHidden, reducedMotion, target]);

  useEffect(() => {
    const normalized = target.startsWith(visible) ? visible : '';
    if (normalized === target || shouldCompleteStreamReveal({
      active,
      backlog: target.length - normalized.length,
      documentHidden,
      reducedMotion,
    })) return undefined;

    let frame = 0;
    let startedAt = 0;
    const step = (timestamp: number) => {
      if (!startedAt) startedAt = timestamp;
      if (timestamp - startedAt < Math.max(16, tickMs)) {
        frame = window.requestAnimationFrame(step);
        return;
      }
      setVisible(target.slice(0, nextRevealLength(normalized, target, mode)));
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [active, documentHidden, mode, reducedMotion, target, tickMs, visible]);

  return {
    pace: streamRevealPace(Math.max(0, target.length - visible.length)),
    text: visible,
  };
}

function useDocumentHidden() {
  const [hidden, setHidden] = useState(() => typeof document !== 'undefined' && document.visibilityState === 'hidden');

  useEffect(() => {
    const update = () => setHidden(document.visibilityState === 'hidden');
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  }, []);

  return hidden;
}
