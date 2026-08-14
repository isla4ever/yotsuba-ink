import { BookOpenCheck, CircleDashed, Sprout } from 'lucide-react';
import { useMemo } from 'react';
import { bibleForeshadowRows, type ForeshadowStatus } from './storyBibleModel';
import type { RunEvent } from '../../contracts';

const statusClass: Record<ForeshadowStatus, string> = {
  投放: 'planted',
  推进: 'advanced',
  回收: 'recovered',
  延后: 'deferred',
};

/** Foreshadow ledger table; unresolved entries sort first. Full gantt view is deferred to a later slice. */
export function ForeshadowSection({ events }: { events: RunEvent[] }) {
  const rows = useMemo(() => bibleForeshadowRows(events), [events]);
  if (!rows.length) {
    return (
      <section className="bible-section bible-section-empty">
        <p className="bible-empty-note">伏笔账本为空。分卷架构定稿后开始登记伏笔的投放与回收计划。</p>
      </section>
    );
  }
  const openCount = rows.filter((row) => row.open).length;
  const chapterCount = new Set(rows.map((row) => row.chapterRange).filter(Boolean)).size;
  return (
    <section className="bible-section bible-foreshadow">
      <dl className="bible-summary-strip">
        <div><dt><Sprout size={13} />伏笔条目</dt><dd>{rows.length}</dd></div>
        <div data-tone={openCount ? 'warning' : 'success'}><dt><CircleDashed size={13} />未闭合</dt><dd>{openCount}</dd></div>
        <div><dt><BookOpenCheck size={13} />涉及章节</dt><dd>{chapterCount}</dd></div>
        <div className="bible-summary-note"><dt>闭合规则</dt><dd>每条伏笔必须在目标章节前回收或显式延后</dd></div>
      </dl>
      <article className="bible-ledger-card">
        <header className="bible-ledger-card-head">
          <h3><Sprout size={15} />伏笔账本</h3>
          <span>{openCount ? `${openCount} 条未闭合，按登记时间倒序` : '全部闭合'}</span>
        </header>
        <table className="bible-table">
          <thead>
            <tr>
              <th scope="col">名称</th>
              <th scope="col">状态</th>
              <th scope="col">投放 / 目标章节</th>
              <th scope="col">最近动作</th>
              <th scope="col">来源</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr className={row.open ? '' : 'closed'} key={row.key}>
                <th scope="row">{row.name}</th>
                <td><span className={`bible-status-badge foreshadow-${statusClass[row.status]}`}>{row.status}</span></td>
                <td>{row.chapterRange ? <span className="bible-chapter-chip">{row.chapterRange}</span> : '—'}</td>
                <td className="bible-table-note">{row.note || '—'}</td>
                <td className="bible-table-source">{row.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </section>
  );
}
