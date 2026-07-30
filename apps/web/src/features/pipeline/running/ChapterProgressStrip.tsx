import { Columns3 } from 'lucide-react';
import {
  chapterCellStatusLabels,
  chapterProgressStrip,
  chapterStripSignature,
  type ChapterCellStatus,
} from './chapterProgressStripModel';
import { useRunEventsSelector } from '../state/pipelineShellContext';

type Props = {
  /** Workflow node id of the Text stage (chapter_progress events carry it). */
  stageId: string;
  compact?: boolean;
};

const summaryOrder: ChapterCellStatus[] = ['completed', 'running', 'review', 'failed', 'planned'];

/**
 * Phase 12 D8: per-chapter progress band under the Text Context Bar. One cell
 * per chapter from the real `chapter_progress_updated` snapshot; status color
 * is never the only channel (per-cell tooltip + accessible label + the count
 * summary alongside). Subscribes to the run-events store (F5) with a
 * signature-equal selector; renders nothing without real chapter data.
 */
export function ChapterProgressStrip({ compact = false, stageId }: Props) {
  const strip = useRunEventsSelector(
    (snapshot) => chapterProgressStrip(snapshot.events, stageId),
    (left, right) => chapterStripSignature(left) === chapterStripSignature(right),
  );
  if (!strip) return null;

  const summary = summaryOrder
    .filter((status) => strip.counts[status] > 0)
    .map((status) => `${chapterCellStatusLabels[status]} ${strip.counts[status]}`)
    .join(' · ');

  return (
    <section aria-label={`章节进度 ${strip.completed}/${strip.total} 章完成`} className={`chapter-progress-strip${compact ? ' compact' : ''}`}>
      {compact ? <span className="sidebar-visually-hidden">{summary}</span> : (
        <header>
          <span><Columns3 size={13} />章节进度</span>
          <em>{strip.completed}/{strip.total} 章 · {summary}</em>
        </header>
      )}
      <div className="chapter-progress-cells" role="list">
        {strip.cells.map((cell) => (
          <span
            aria-label={cell.description}
            className={`chapter-progress-cell ${cell.status}`}
            key={cell.chapter}
            role="listitem"
            title={cell.description}
          />
        ))}
      </div>
    </section>
  );
}
