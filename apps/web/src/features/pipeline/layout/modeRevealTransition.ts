import { flushSync } from 'react-dom';

/** Phase 11.1 mode-switch radial reveal (View Transitions, native API).
 *
 * Degradation matrix:
 * - VT supported x motion allowed  -> circle clip-path reveal from the click point (360ms).
 * - VT supported x reduced motion  -> instant switch, no view transition.
 * - VT unsupported x any           -> instant switch.
 * The switch callback itself never issues business requests; it only flips React state.
 */

export const MODE_REVEAL_DURATION_MS = 360;
export const MODE_REVEAL_EASING = 'cubic-bezier(0.16, 1, 0.3, 1)';

export type ModeRevealOrigin = { x: number; y: number };

export type ModeRevealDocument = {
  startViewTransition?: (update: () => void) => { ready: Promise<void> };
  documentElement: {
    clientWidth: number;
    clientHeight: number;
    animate: (
      keyframes: { clipPath: string[] },
      options: { duration: number; easing: string; pseudoElement: string },
    ) => unknown;
  };
};

export function supportsViewTransitions(doc: ModeRevealDocument | undefined): boolean {
  return typeof doc?.startViewTransition === 'function';
}

/** Radius from the click point to the farthest viewport corner. */
export function maxRevealRadius(origin: ModeRevealOrigin, width: number, height: number): number {
  return Math.hypot(Math.max(origin.x, width - origin.x), Math.max(origin.y, height - origin.y));
}

function defaultDocument(): ModeRevealDocument | undefined {
  return typeof document === 'undefined' ? undefined : (document as unknown as ModeRevealDocument);
}

type RevealOptions = {
  origin?: ModeRevealOrigin;
  reducedMotion: boolean;
  doc?: ModeRevealDocument;
};

export function runModeRevealTransition(
  apply: () => void,
  { origin, reducedMotion, doc = defaultDocument() }: RevealOptions,
): 'view-transition' | 'instant' {
  if (!doc || reducedMotion || !origin || !supportsViewTransitions(doc)) {
    apply();
    return 'instant';
  }
  // flushSync makes the mode-class swap land inside the transition snapshot
  // (Not A Number / Akash Hamirwasia React View Transitions pattern).
  const transition = doc.startViewTransition!(() => flushSync(apply));
  transition.ready
    .then(() => {
      const radius = maxRevealRadius(origin, doc.documentElement.clientWidth, doc.documentElement.clientHeight);
      doc.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${origin.x}px ${origin.y}px)`,
            `circle(${Math.ceil(radius)}px at ${origin.x}px ${origin.y}px)`,
          ],
        },
        { duration: MODE_REVEAL_DURATION_MS, easing: MODE_REVEAL_EASING, pseudoElement: '::view-transition-new(root)' },
      );
    })
    .catch(() => {
      /* Reveal is progressive enhancement; the state switch already happened. */
    });
  return 'view-transition';
}
