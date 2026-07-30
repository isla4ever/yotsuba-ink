import { AlertTriangle, BarChart3, LocateFixed, ShieldCheck, X } from 'lucide-react';
import { useState } from 'react';
import type { ChapterQualityRepairTarget, QualityEvent, RunEvent, WorkflowStage } from '../../contracts';
import type { ChapterReviewInsight } from '../writingArtifactModel';

type Props = {
  events: RunEvent[];
  stages: WorkflowStage[];
  chapterReview?: ChapterReviewInsight;
  onRepairQualityFinding?: (target: ChapterQualityRepairTarget) => void;
};

export function QualityMonitorPanel({ chapterReview, events, stages, onRepairQualityFinding }: Props) {
  const [detailOpen, setDetailOpen] = useState(false);
  const actual = events
    .filter((event) => event.type === 'quality_check_completed' || event.type === 'quality_recheck_completed')
    .map((event) => {
      if (event.quality) return event.quality as QualityEvent;
      if (event.quality_report) {
        return {
          node_id: event.quality_report.node_id,
          node_type: event.quality_report.node_type,
          label: event.type === 'quality_recheck_completed' ? `${event.chapter ?? event.quality_report.label}复检` : event.quality_report.label,
          score: event.quality_report.score,
          min_score: 0.8,
          passed: event.quality_report.passed,
          checks: { findings: event.quality_report.findings.length },
          warnings: event.quality_report.findings.map((item) => item.message),
        } satisfies QualityEvent;
      }
      return null;
    })
    .filter(Boolean) as QualityEvent[];
  const reviewQuality = chapterReview?.qualityRecheck
    ? qualityFromReview(chapterReview)
    : null;
  const qualityEvents = reviewQuality
    ? [reviewQuality, ...actual.filter((item) => item.label !== reviewQuality.label || item.score !== reviewQuality.score)]
    : actual;
  const avg = qualityEvents.length ? qualityEvents.reduce((sum, event) => sum + event.score, 0) / qualityEvents.length : 0;
  const blocked = qualityEvents.filter((item) => !item.passed).length;
  const latest = qualityEvents[0];
  const repairTargets = chapterReview?.qualityRecheck?.repair_targets ?? [];
  return (
    <section className="config-section runtime-insight-card compact-widget quality-monitor-widget">
      <button className="widget-open-button" onClick={() => setDetailOpen(true)} type="button">
        <span><ShieldCheck size={16} />质量检查</span>
        <b>{qualityEvents.length ? avg.toFixed(2) : '--'}</b>
      </button>
      <div className="widget-meter">
        <i style={{ width: `${Math.min(100, avg * 100)}%` }} />
      </div>
      <div className="widget-kpis">
        <span><strong>{blocked}</strong>警告</span>
        <span><strong>{qualityEvents.length}</strong>检查</span>
        <span><strong>{stages.filter((stage) => stage.type !== 'cover_image' && stage.type !== 'export_artifact').length}</strong>阶段</span>
      </div>
      <p>{latest ? latest.warnings[0] ?? `${latest.label} 已完成本阶段质量检查` : '等待第一次质量检查'}</p>
      {detailOpen ? (
        <div className="quality-inline-detail">
          <div className="quality-inline-detail-head">
            <span><BarChart3 size={14} />质量检查明细</span>
            <button aria-label="收起质量详情" className="mini-close-button" onClick={() => setDetailOpen(false)} type="button"><X size={14} /></button>
          </div>
          <div className="quality-list expanded">
            {repairTargets.length ? (
              <div className="quality-repair-list">
                {repairTargets.slice(0, 3).map((target) => (
                  <div key={target.finding_id}>
                    <span>{target.message}</span>
                    {target.locatable && onRepairQualityFinding ? (
                      <button onClick={() => {
                        onRepairQualityFinding(target);
                        setDetailOpen(false);
                      }} type="button"><LocateFixed size={12} />定位修订</button>
                    ) : <small>{target.instruction}</small>}
                  </div>
                ))}
              </div>
            ) : null}
            {qualityEvents.map((event) => (
              <article className={event.passed ? 'passed' : 'blocked'} key={`${event.node_id}-${event.score}`}>
                <div>
                  <strong>{event.label}</strong>
                  <span>{event.score.toFixed(2)} / {event.min_score.toFixed(2)}</span>
                </div>
                <p>{event.warnings[0] ?? '连续性、人物一致性、世界观冲突通过'}</p>
              </article>
            ))}
            {!qualityEvents.length ? <p className="runtime-widget-empty">等待真实质量检查事件。</p> : null}
          </div>
          <p className="muted"><AlertTriangle size={14} />仅展示本次运行累计的质量事件，正文阶段会优先呈现章节级风险。</p>
        </div>
      ) : null}
    </section>
  );
}

function qualityFromReview(review: ChapterReviewInsight): QualityEvent {
  const report = review.qualityRecheck!.report;
  return {
    node_id: report.node_id,
    node_type: report.node_type,
    label: `${review.chapter}复检`,
    score: report.score,
    min_score: 0.8,
    passed: report.passed,
    checks: { findings: report.findings.length },
    warnings: report.findings.map((item) => item.message),
  };
}
