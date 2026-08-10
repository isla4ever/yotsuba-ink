import { useRef } from 'react';
import type { KeyboardEvent } from 'react';
import type { TimelineTick } from './characterNetworkModel';

type Props = {
  ticks: TimelineTick[];
  activeId: string;
  onSelect: (tickId: string) => void;
};

/**
 * Chapter timeline for the character network. Radio-group semantics (not a
 * slider) because ticks are discrete, labelled, non-uniformly spaced points;
 * arrow keys move the viewpoint per the WAI-ARIA radio pattern, with roving
 * tabindex so the group is a single tab stop. Selecting a tick is a pure local
 * filter — there is no autoplay and no looping motion.
 */
export function NetworkTimeline({ activeId, onSelect, ticks }: Props) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const activeIndex = Math.max(0, ticks.findIndex((tick) => tick.id === activeId));

  const moveTo = (index: number) => {
    const next = ticks[Math.min(ticks.length - 1, Math.max(0, index))];
    if (!next || next.id === activeId) return;
    onSelect(next.id);
    window.requestAnimationFrame(() => {
      trackRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = {
      ArrowDown: activeIndex + 1,
      ArrowLeft: activeIndex - 1,
      ArrowRight: activeIndex + 1,
      ArrowUp: activeIndex - 1,
      End: ticks.length - 1,
      Home: 0,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    moveTo(moves[event.key]);
  };

  return (
    <div className="bible-network-timeline">
      <div aria-label="关系网时间轴视点" className="bible-timeline-track" onKeyDown={onKeyDown} ref={trackRef} role="radiogroup">
        {ticks.map((tick, index) => (
          <button
            aria-checked={tick.id === activeId}
            className={`bible-timeline-tick${tick.id === activeId ? ' active' : ''}${tick.type === 'chapter' ? ' chapter' : ''}`}
            key={tick.id}
            onClick={() => moveTo(index)}
            role="radio"
            tabIndex={tick.id === activeId ? 0 : -1}
            type="button"
          >
            {tick.label}
          </button>
        ))}
      </div>
    </div>
  );
}
