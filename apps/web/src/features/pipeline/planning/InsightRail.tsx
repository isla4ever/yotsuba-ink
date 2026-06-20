import { Suspense, lazy } from 'react';
import { AlertTriangle, Database, ShieldCheck } from 'lucide-react';
import type { QualityEvent, RunEvent, WorkflowDefinition } from '../contracts';

const CharacterForceGraphPanel = lazy(async () => {
  const module = await import('../running/insights/CharacterForceGraphPanel');
  return { default: module.CharacterForceGraphPanel };
});

type Props = {
  workflow: WorkflowDefinition;
  events: RunEvent[];
};

const fallbackQuality: QualityEvent[] = [
  { node_id: 'summary', node_type: 'summary', label: '全书梗概', score: 0.88, min_score: 0.8, passed: true, checks: {}, warnings: [] },
  { node_id: 'detail', node_type: 'detail_outline', label: '章节细纲', score: 0.83, min_score: 0.8, passed: true, checks: {}, warnings: ['第 2 章钩子可加强'] },
  { node_id: 'text', node_type: 'chapter_text', label: '正文生成', score: 0.81, min_score: 0.84, passed: false, checks: {}, warnings: ['低于正文阶段最低质量分'] },
];

export function InsightRail({ workflow, events }: Props) {
  const reads = events.filter((event) => event.type === 'memory_context_loaded');
  const writes = events.filter((event) => event.type === 'memory_writeback_completed');
  const qualityEvents = events
    .filter((event) => event.type === 'quality_check_completed' && event.quality)
    .map((event) => event.quality as QualityEvent);
  const quality = qualityEvents.length ? qualityEvents : fallbackQuality;
  const avg = quality.reduce((sum, item) => sum + item.score, 0) / quality.length;
  const warnings = quality.filter((item) => !item.passed || item.warnings.length);

  return (
    <aside className="insight-rail">
      <Suspense fallback={<GraphPanelFallback title="人物关系网加载中..." />}>
        <CharacterForceGraphPanel events={events} />
      </Suspense>

      <section className="insight-card memory-quality-card">
        <div className="insight-card-head">
          <div>
            <p className="eyebrow">Runtime Layers</p>
            <h3><Database size={16} />Wiki + 质量监控</h3>
          </div>
          <span className={warnings.length ? 'rail-status warn' : 'rail-status ok'}>
            {warnings.length ? `${warnings.length} 警告` : '稳定'}
          </span>
        </div>

        <div className="rail-stats">
          <strong>{reads.length}<span>记忆读取</span></strong>
          <strong>{writes.length}<span>Wiki 写回</span></strong>
          <strong>{avg.toFixed(2)}<span>质量均分</span></strong>
        </div>

        <div className="constraint-chips">
          {['人物状态', '世界观硬设定', '伏笔状态', '章节摘要', '关系拓扑'].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>

        <div className="rail-list">
          {quality.slice(0, 4).map((item) => (
            <article className={item.passed ? 'passed' : 'blocked'} key={`${item.node_id}-${item.score}`}>
              <ShieldCheck size={14} />
              <div>
                <strong>{item.label}</strong>
                <span>Q {item.score.toFixed(2)} / {item.min_score.toFixed(2)}</span>
              </div>
            </article>
          ))}
          {warnings.slice(0, 2).map((item) => (
            <article className="warning" key={`warning-${item.node_id}`}>
              <AlertTriangle size={14} />
              <div>
                <strong>{item.label}</strong>
                <span>{item.warnings[0] ?? '低于最低质量分'}</span>
              </div>
            </article>
          ))}
        </div>

        <div className="stage-policy-strip">
          {workflow.nodes.filter((stage) => stage.type !== 'export_artifact').map((stage) => (
            <span key={stage.id}>{stage.label} · {stage.quality_policy.min_score.toFixed(2)}</span>
          ))}
        </div>
      </section>
    </aside>
  );
}

function GraphPanelFallback({ title }: { title: string }) {
  return (
    <section className="insight-card graph-panel-fallback" aria-live="polite">
      <div className="insight-card-head">
        <div>
          <p className="eyebrow">Character Graph</p>
          <h3>{title}</h3>
        </div>
      </div>
    </section>
  );
}
