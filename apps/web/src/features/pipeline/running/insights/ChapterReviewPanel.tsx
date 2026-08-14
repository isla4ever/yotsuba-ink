import { AlertTriangle, CheckCircle2, MinusCircle } from 'lucide-react';
import type { RunEvent } from '../../contracts';
import {
  blockingCount,
  chapterReviewLanes,
  reviewRoleLabel,
  severityLabel,
  type ReviewLane,
} from './chapterReviewFindings';

function laneVerdict(lane: ReviewLane) {
  if (!lane.available) return '无结论';
  return lane.findings.length ? `${lane.findings.length} 条` : '通过';
}

type Props = {
  chapterId: string;
  events: RunEvent[];
  /** Extra line above the lanes, e.g. the chapter capacity summary. */
  summary?: string;
};

/**
 * What the reviewers actually said about this chapter. The author decides
 * whether to accept the draft, so the findings themselves have to be readable
 * here — an event-type list cannot support that decision.
 */
export function ChapterReviewPanel({ chapterId, events, summary }: Props) {
  const lanes = chapterReviewLanes(events, chapterId);
  const blocking = blockingCount(lanes);
  return (
    <section className="config-section runtime-insight-card chapter-review-panel">
      <header className="chapter-review-head">
        <h3>审稿与人工质量门</h3>
        <span className={blocking ? 'chapter-review-verdict blocking' : 'chapter-review-verdict clear'}>
          {blocking ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
          {blocking ? `${blocking} 条阻断问题` : lanes.length ? '未发现阻断问题' : '尚未审稿'}
        </span>
      </header>
      {summary ? <p>{summary}</p> : null}
      {lanes.length ? (
        <ul className="chapter-review-lanes">
          {lanes.map((lane) => (
            <li key={lane.role}>
              <div className="chapter-review-lane-head">
                <strong>{reviewRoleLabel(lane.role)}</strong>
                {lane.available ? null : <em><MinusCircle size={12} />{lane.required ? '必需审稿未出结论' : '未运行'}</em>}
                <span>{laneVerdict(lane)}</span>
              </div>
              {lane.findings.length ? (
                <ol className="chapter-review-findings">
                  {lane.findings.map((finding, index) => (
                    <li className={finding.severity} key={`${lane.role}-${finding.code}-${index}`}>
                      <span className="chapter-review-severity">{severityLabel(finding.severity)}</span>
                      <p>{finding.claim}</p>
                      {finding.evidence ? <blockquote>{finding.evidence}</blockquote> : null}
                    </li>
                  ))}
                </ol>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="chapter-review-empty">本章还没有审稿结果。正文生成完成后，连续性、人物一致性与文风三条审稿线会在这里给出结论。</p>
      )}
    </section>
  );
}
