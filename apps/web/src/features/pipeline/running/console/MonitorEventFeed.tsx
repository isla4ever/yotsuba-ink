import { useMemo, useRef } from 'react';
import type { RunEvent } from '../../contracts';
import { runEventLabel } from '../../lib/runEventLabels';
import { eventStageId } from '../stageRunUtils';

type Props = {
  /** Collapsed stays mounted so the column can fade and shrink instead of vanishing. */
  collapsed?: boolean;
  events: RunEvent[];
  /** False while the console is still on its entry loader: the backlog must not animate in. */
  settled?: boolean;
  stageLabels: Record<string, string>;
};

const FEED_LIMIT = 160;
/** Checkpoints and raw deltas are runtime plumbing, not narration the author needs. */
const HIDDEN_TYPES = new Set(['checkpoint.saved', 'provider.delta']);

export function MonitorEventFeed({ collapsed = false, events, settled = true, stageLabels }: Props) {
  const entries = useMemo(
    () => events.filter((event) => !HIDDEN_TYPES.has(event.type)).slice(0, FEED_LIMIT),
    [events],
  );
  const historical = useHistoricalIds(entries, settled);
  return (
    <section aria-hidden={collapsed} aria-label="运行日志" className={`monitor-feed${collapsed ? ' is-collapsed' : ''}`}>
      <header className="monitor-feed-head">
        <h3>运行日志</h3>
        <span>{entries.length ? `最近 ${entries.length} 条 · 最新在上` : ''}</span>
      </header>
      {entries.length ? (
        <ol className="monitor-feed-list">
          {entries.map((event) => (
            <li
              className={`monitor-feed-item kind-${event.type.split('.')[0]}${historical.has(event.event_id) ? '' : ' is-live'}`}
              key={event.event_id}
            >
              <span className="monitor-feed-time">{clockTime(event.occurred_at)}</span>
              <span className="monitor-feed-copy">
                <strong>{eventText(event)}</strong>
                <small>
                  {stageLabels[eventStageId(event)] ?? eventStageId(event)}
                  {event.chapter_id ? ` · ${event.chapter_id}` : ''}
                </small>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="monitor-feed-empty">运行事件将实时出现在这里。</p>
      )}
    </section>
  );
}

/**
 * Everything already in the buffer when the console settles is history: it
 * renders statically so re-entering a finished run never replays a log storm.
 */
function useHistoricalIds(entries: RunEvent[], settled: boolean) {
  const baselineRef = useRef<Set<string> | null>(null);
  if (!settled) return new Set(entries.map((event) => event.event_id));
  if (!baselineRef.current) baselineRef.current = new Set(entries.map((event) => event.event_id));
  return baselineRef.current;
}

function eventText(event: RunEvent) {
  if (event.type === 'review.completed' || event.type === 'review.started' || event.type === 'review.unavailable') {
    const role = typeof event.payload?.role === 'string' ? event.payload.role : '';
    const findings = Array.isArray(event.payload?.findings) ? ` · ${event.payload.findings.length} 个发现` : '';
    return `${runEventLabel(event.type)}${role ? `（${role}）` : ''}${event.type === 'review.completed' ? findings : ''}`;
  }
  if (event.type === 'evidence.proposed') {
    const claim = typeof event.payload?.claim === 'string' ? event.payload.claim : '';
    return claim ? `事实提案：${truncate(claim, 42)}` : runEventLabel(event.type);
  }
  return runEventLabel(event.type);
}

function truncate(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

function clockTime(value: string) {
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) return '';
  return time.toLocaleTimeString('zh-CN', { hour12: false });
}
