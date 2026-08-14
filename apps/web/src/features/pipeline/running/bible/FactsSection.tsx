import { CheckCircle2, Database, ShieldAlert } from 'lucide-react';
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
  const activeCount = rows.filter((row) => row.status === 'active').length;
  const pendingCount = rows.filter((row) => row.status === 'pending').length;
  return (
    <section className="bible-section bible-facts">
      <dl className="bible-summary-strip">
        <div><dt><Database size={13} />写回事务</dt><dd>{rows.length}</dd></div>
        <div data-tone="success"><dt><CheckCircle2 size={13} />生效中</dt><dd>{activeCount}</dd></div>
        <div data-tone={pendingCount ? 'warning' : undefined}><dt><ShieldAlert size={13} />冲突待裁决</dt><dd>{pendingCount}</dd></div>
        <div className="bible-summary-note"><dt>正典语义</dt><dd>正文定稿通过写回提案后成为不可矛盾的事实基线</dd></div>
      </dl>
      <article className="bible-ledger-card">
        <header className="bible-ledger-card-head">
          <h3><Database size={15} />正典事实</h3>
          <span>{pendingCount ? `${pendingCount} 条冲突待裁决，优先处理` : '无未决冲突'}</span>
        </header>
        <ul className="bible-fact-list bible-canon-list">
          {rows.map((row) => (
            <li className={`bible-canon-row ${row.status}`} key={row.key}>
              <span aria-hidden="true" className={`bible-canon-icon ${row.status}`}>
                {row.status === 'active' ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
              </span>
              <span className="bible-fact-text">
                <strong>{row.target || '未命名对象'}</strong>
                {row.claim ? <span className="bible-canon-claim">{row.claim}</span> : null}
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
