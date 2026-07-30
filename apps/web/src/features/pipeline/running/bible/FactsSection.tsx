import { Database } from 'lucide-react';
import { useMemo } from 'react';
import { bibleCanonRows, type BibleCanonStatus } from './storyBibleModel';
import type { RunEvent } from '../../contracts';

const statusLabels: Record<BibleCanonStatus, string> = {
  active: '生效中',
  pending: '冲突待裁决',
  superseded: '已被替代',
};

/** Canon fact ledger: pending conflicts highlighted first, superseded facts de-emphasized last. */
export function FactsSection({ events }: { events: RunEvent[] }) {
  const rows = useMemo(() => bibleCanonRows(events), [events]);
  if (!rows.length) {
    return (
      <section className="bible-section bible-section-empty">
        <p className="bible-empty-note">正典事实尚未写回——正文章节定稿并通过写回提案后，这里会展示正典事实账本。</p>
      </section>
    );
  }
  const pendingCount = rows.filter((row) => row.status === 'pending').length;
  return (
    <section className="bible-section bible-facts">
      <article className="bible-list-card">
        <h3><Database size={15} />正典事实（{rows.length} 条{pendingCount ? ` · ${pendingCount} 条冲突待裁决` : ''}）</h3>
        <ul className="bible-fact-list">
          {rows.map((row) => (
            <li className={`bible-canon-row ${row.status}`} key={row.key}>
              <span className="bible-fact-text">
                <strong>{row.target || '未命名对象'}</strong>
                {row.claim ? ` · ${row.claim}` : ''}
                {row.detail ? <em className="bible-canon-conflict-detail">{row.detail}</em> : null}
              </span>
              <span className={`bible-status-badge canon-${row.status}`}>{statusLabels[row.status]}</span>
              <small className="bible-fact-source">{row.chapter ? `来源章节：${row.chapter}` : '正文写回'}</small>
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}
