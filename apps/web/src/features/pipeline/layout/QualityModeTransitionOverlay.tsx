import { AnimatePresence, motion } from 'motion/react';
import { createPortal } from 'react-dom';
import type { QualityMode } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';

/** Phase 11.1 mode badge rhythm: 180ms enter -> dwell -> 120ms exit.
 * The owner (AppHeader) clears the notice at MODE_NOTICE_DWELL_MS. */
export const MODE_NOTICE_ENTER_MS = 180;
export const MODE_NOTICE_DWELL_MS = 900;
export const MODE_NOTICE_EXIT_MS = 120;

export function modeNoticeTiming(reducedMotion: boolean) {
  return {
    enter: reducedMotion ? 0 : MODE_NOTICE_ENTER_MS,
    exit: reducedMotion ? 0 : MODE_NOTICE_EXIT_MS,
  };
}

type Props = {
  mode: QualityMode | null;
};

export function QualityModeTransitionOverlay({ mode }: Props) {
  const reducedMotion = useReducedMotionPreference();
  return createPortal(<ModeTransitionScene mode={mode} reducedMotion={reducedMotion} />, document.body);
}

/** Non-interactive status scene: light mode-tinted wash + surface-2 badge card. */
export function ModeTransitionScene({ mode, reducedMotion }: { mode: QualityMode | null; reducedMotion: boolean }) {
  const timing = modeNoticeTiming(reducedMotion);
  return (
    <AnimatePresence initial={false}>
      {mode ? (
        <motion.div
          animate={{ opacity: 1 }}
          aria-live="polite"
          className={`quality-mode-transition-overlay mode-${mode}`}
          exit={{ opacity: 0, transition: { duration: timing.exit / 1000 } }}
          initial={{ opacity: 0 }}
          role="status"
          transition={{ duration: timing.enter / 1000, ease: [0.16, 1, 0.3, 1] }}
        >
          <motion.section
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="quality-mode-transition-card"
            exit={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 0.985, y: -4, transition: { duration: timing.exit / 1000 } }}
            initial={reducedMotion ? false : { opacity: 0, scale: 0.97, y: 6 }}
            transition={{ duration: timing.enter / 1000, ease: [0.16, 1, 0.3, 1] }}
          >
            <ModeGlyph mode={mode} />
            <div>
              <span>创作模式</span>
              <h2>{qualityModeProfiles[mode].title}</h2>
              <p>{qualityModeProfiles[mode].intervention} · {qualityModeProfiles[mode].cost}</p>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/** Geometric mode glyphs, stroke draw-in handled in CSS (one-shot, pathLength-normalized).
 * fast = three progressive feather chevrons / balanced = concentric rings / deep = diamond prism. */
function ModeGlyph({ mode }: { mode: QualityMode }) {
  return (
    <span aria-hidden="true" className="quality-mode-transition-glyph">
      <svg fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="24">
        {glyphShapes[mode]}
      </svg>
    </span>
  );
}

const glyphShapes: Record<QualityMode, JSX.Element> = {
  fast: (
    <>
      <path className="glyph-step-1" d="m4 5 6 7-6 7" pathLength={1} />
      <path className="glyph-step-2" d="m10 5 6 7-6 7" pathLength={1} />
      <path className="glyph-step-3" d="m16 5 6 7-6 7" pathLength={1} />
    </>
  ),
  balanced: (
    <>
      <circle className="glyph-step-1" cx="12" cy="12" pathLength={1} r="9" />
      <circle className="glyph-step-2" cx="12" cy="12" pathLength={1} r="4.5" />
    </>
  ),
  deep: (
    <>
      <path className="glyph-step-1" d="M12 3l9 9-9 9-9-9z" pathLength={1} />
      <path className="glyph-step-2" d="M12 7.5l4.5 4.5-4.5 4.5L7.5 12z" pathLength={1} />
      <path className="glyph-step-3" d="M12 3v4.5m0 9V21" pathLength={1} />
    </>
  ),
};
