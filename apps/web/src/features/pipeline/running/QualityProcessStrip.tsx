import { ShieldAlert, ShieldCheck } from 'lucide-react';
import type { RunEvent } from '../contracts';
import { qualityEventLabel, qualityEventText } from './stageRunUtils';

export function QualityProcessStrip({ events, stageId }: { events: RunEvent[]; stageId: string }) {
  const relevant = events
    .filter((event) => event.node_id === stageId && [
      'chapter_context_built',
      'quality_check_started',
      'quality_check_completed',
      'revision_directive_created',
      'revision_applied',
      'quality_recheck_completed',
      'story_bible_updated',
      'manual_intervention_required',
    ].includes(event.type))
    .slice(0, 6);
  if (!relevant.length) return null;
  return (
    <section className="quality-process-strip">
      <div className="quality-process-head">
        <ShieldCheck size={15} />
        <span>质量闭环</span>
      </div>
      <div className="quality-process-list">
        {relevant.map((event, index) => (
          <article className={event.type === 'manual_intervention_required' ? 'blocking' : ''} key={`${event.type}-${event.chapter ?? ''}-${index}`}>
            {event.type === 'manual_intervention_required' ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />}
            <strong>{qualityEventLabel(event.type)}</strong>
            <span>{qualityEventText(event)}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
