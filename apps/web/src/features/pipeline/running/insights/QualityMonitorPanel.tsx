import { AlertTriangle, ShieldCheck } from 'lucide-react';
import type { QualityEvent, RunEvent, WorkflowStage } from '../../contracts';

type Props = {
  events: RunEvent[];
  stages: WorkflowStage[];
};

const fallback: QualityEvent[] = [
  { node_id: 'summary', node_type: 'summary', label: '全书梗概', score: 0.88, min_score: 0.8, passed: true, checks: { continuity: true, character_consistency: true, worldbuilding_conflict: true }, warnings: [] },
  { node_id: 'detail', node_type: 'detail_outline', label: '章节细纲', score: 0.83, min_score: 0.8, passed: true, checks: { foreshadowing: true, hook: true }, warnings: ['第 2 章钩子可加强'] },
  { node_id: 'text', node_type: 'chapter_text', label: '正文生成', score: 0.81, min_score: 0.84, passed: false, checks: { continuity: true, repetition: false }, warnings: ['低于正文阶段最低质量分，建议重试'] },
];

export function QualityMonitorPanel({ events, stages }: Props) {
  const actual = events
    .filter((event) => event.type === 'quality_check_completed' && event.quality)
    .map((event) => event.quality as QualityEvent);
  const qualityEvents = actual.length ? actual : fallback;
  const avg = qualityEvents.reduce((sum, event) => sum + event.score, 0) / qualityEvents.length;
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><ShieldCheck size={16} />质量监控</h3>
        <div className="quality-score">
          <strong>{avg.toFixed(2)}</strong>
          <span>平均质量分 · {qualityEvents.filter((item) => !item.passed).length} 个拦截/警告</span>
        </div>
      </section>
      <section className="config-section">
        <h3><AlertTriangle size={16} />检查项</h3>
        <div className="quality-list">
          {qualityEvents.map((event) => (
            <article className={event.passed ? 'passed' : 'blocked'} key={`${event.node_id}-${event.score}`}>
              <div>
                <strong>{event.label}</strong>
                <span>{event.score.toFixed(2)} / {event.min_score.toFixed(2)}</span>
              </div>
              <p>{event.warnings[0] ?? '连续性、人物一致性、世界观冲突通过'}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="config-section">
        <h3>阶段质量策略</h3>
        <div className="field-list">
          {stages.filter((stage) => stage.type !== 'cover_image' && stage.type !== 'export_artifact').map((stage) => (
            <article key={stage.id}>
              <strong>{stage.label}</strong>
              <span>最低分 {stage.quality_policy.min_score.toFixed(2)} · {stage.quality_policy.retry_on_fail ? '失败自动重试' : '仅警告'}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
