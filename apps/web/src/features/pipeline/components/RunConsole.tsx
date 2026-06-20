import { Activity, ChevronDown, ChevronUp, Database, FileText, Timer } from 'lucide-react';
import type { RunEvent } from '../types/workflow';
import { formatResult } from '../utils/workflow';
import { runtimeTextForUi } from '../utils/display';

type Props = {
  events: RunEvent[];
  memoryEvents: RunEvent[];
  latestResult: string;
  collapsed: boolean;
  onToggle: () => void;
};

export function RunConsole({ events, memoryEvents, latestResult, collapsed, onToggle }: Props) {
  return (
    <section className={collapsed ? 'run-console collapsed' : 'run-console'}>
      <button className="console-toggle" onClick={onToggle}>
        <Activity size={15} />
        <span>运行台</span>
        <strong>{runtimeTextForUi(events[0]?.type ?? '等待运行')}</strong>
        {collapsed ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
      </button>
      <div className="console-content">
        <div className="console-card">
        <h3><Activity size={16} />运行日志</h3>
        <div className="console-list">
          {events.slice(0, 8).map((event, index) => (
            <article key={`${event.type}-${event.node_id ?? 'run'}-${index}`}>
              <strong>{runtimeTextForUi(event.type)}</strong>
              <span>{event.label ?? event.node_id ?? event.run_id}</span>
            </article>
          ))}
        </div>
      </div>
      <div className="console-card">
        <h3><Database size={16} />Wiki / Memory</h3>
        <div className="metric-row">
          <span>读取 {memoryEvents.filter((event) => event.type === 'memory_context_loaded').length}</span>
          <span>写回 {memoryEvents.filter((event) => event.type === 'memory_writeback_completed').length}</span>
        </div>
        <div className="console-list compact">
          {memoryEvents.slice(0, 5).map((event, index) => (
            <article key={`${event.type}-${event.node_id ?? 'memory'}-${index}`}>
              <strong>{event.type === 'memory_context_loaded' ? '读取约束' : '写回记忆'}</strong>
              <span>{event.label ?? event.node_id}</span>
            </article>
          ))}
        </div>
      </div>
      <div className="console-card artifact-card">
        <h3><FileText size={16} />阶段产物</h3>
        <pre>{latestResult || formatResult('等待运行')}</pre>
      </div>
      <div className="console-card">
        <h3><Timer size={16} />成本 / 耗时</h3>
        <div className="metric-row vertical">
          <span>Token：演示估算</span>
          <span>耗时：实时统计待接入</span>
          <span>费用：按 Provider 估算</span>
        </div>
      </div>
      </div>
    </section>
  );
}
