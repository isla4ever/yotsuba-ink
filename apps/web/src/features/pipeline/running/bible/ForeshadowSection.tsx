import { Sprout } from 'lucide-react';
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
        <p className="bible-empty-note">伏笔账本为空——分卷大纲定稿后开始登记伏笔的投放与回收计划。</p>
      </section>
    );
  }
  const openCount = rows.filter((row) => row.open).length;
  return (
    <section className="bible-section bible-foreshadow">
      <article className="bible-list-card">
        <h3><Sprout size={15} />伏笔账本（{rows.length} 条 · 未闭合 {openCount}）</h3>
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
                <td>{row.chapterRange || '—'}</td>
                <td>{row.note || '—'}</td>
                <td>{row.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </section>
  );
}
