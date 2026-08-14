import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';
import { useRef, type ElementType } from 'react';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';

gsap.registerPlugin(useGSAP);

type Props = {
  as?: ElementType;
  className?: string;
  id?: string;
  /** Character stagger in seconds; larger reads slower and more deliberate. */
  stagger?: number;
  text: string;
  title?: string;
};

/**
 * Per-character entrance for surface titles (SplitText pattern). The full string
 * stays in the accessibility tree; only the visual glyph spans animate, and
 * reduced-motion renders plain text with no split at all.
 */
export function RevealText({ as, className = '', id, stagger = 0.018, text, title }: Props) {
  const Tag = (as ?? 'span') as ElementType;
  const rootRef = useRef<HTMLElement | null>(null);
  const reducedMotion = useReducedMotionPreference();

  useGSAP(() => {
    if (reducedMotion || !rootRef.current) return;
    const glyphs = rootRef.current.querySelectorAll('[data-reveal-glyph]');
    if (!glyphs.length) return;
    gsap.fromTo(
      glyphs,
      { opacity: 0, y: '0.35em' },
      { duration: 0.42, ease: 'power3.out', opacity: 1, stagger, y: 0 },
    );
  }, { dependencies: [reducedMotion, stagger, text], scope: rootRef });

  if (reducedMotion) {
    return <Tag className={className} id={id} title={title}>{text}</Tag>;
  }
  return (
    <Tag className={`nw-reveal-text ${className}`.trim()} id={id} ref={rootRef} title={title}>
      <span aria-hidden="true" className="nw-reveal-text-glyphs">
        {[...text].map((glyph, index) => (
          <span data-reveal-glyph key={`${glyph}-${index}`}>{glyph === ' ' ? '\u00a0' : glyph}</span>
        ))}
      </span>
      <span className="nw-reveal-text-source">{text}</span>
    </Tag>
  );
}
