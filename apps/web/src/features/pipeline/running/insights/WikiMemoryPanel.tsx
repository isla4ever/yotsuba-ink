import { Database, Link2 } from 'lucide-react';
import type { RunEvent } from '../../contracts';

type Props = {
  events: RunEvent[];
};

export function WikiMemoryPanel({ events }: Props) {
  const reads = events.filter((event) => event.type === 'memory_context_loaded');
  const writes = events.filter((event) => event.type === 'memory_writeback_completed');
  const hits = ['人物状态', '世界观硬设定', '未回收伏笔', '章节摘要', '关系拓扑'];
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><Database size={16} />Wiki / Memory 横切层</h3>
        <div className="stats-grid">
          <strong>{reads.length}<span>读取约束</span></strong>
          <strong>{writes.length}<span>写回页面</span></strong>
          <strong>{hits.length}<span>约束类型</span></strong>
        </div>
      </section>
      <section className="config-section">
        <h3><Link2 size={16} />约束命中</h3>
        <div className="chip-grid">
          {hits.map((hit) => <span key={hit}>{hit}</span>)}
        </div>
      </section>
      <section className="config-section">
        <h3>最近记忆事件</h3>
        <div className="field-list">
          {[...reads, ...writes].slice(0, 8).map((event, index) => (
            <article key={`${event.type}-${event.node_id}-${index}`}>
              <strong>{event.type === 'memory_context_loaded' ? '读取约束' : '写回记忆'}</strong>
              <span>{event.label ?? event.node_id}</span>
              <small>{event.type}</small>
            </article>
          ))}
          {!reads.length && !writes.length ? <p className="muted">运行后这里会显示每个阶段实际读取和写回的 Wiki 记录。</p> : null}
        </div>
      </section>
    </div>
  );
}
