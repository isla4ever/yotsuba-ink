import { ChevronLeft, Database, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react';
import type { WritingChapter } from './writingArtifactModel';
import { writingQualityFindings, writingQualityScore } from './writingReviewModel';

type Props = {
  chapter: WritingChapter;
  onExpand: () => void;
};

export function WritingReviewRail({ chapter, onExpand }: Props) {
  const findings = writingQualityFindings(chapter);
  const score = writingQualityScore(chapter);
  const pendingProposal = chapter.writeback_proposal?.status === 'pending';
  return (
    <aside aria-label="本章审校摘要" className="writing-review-rail">
      <button aria-label="展开审校视图" className="writing-rail-expand" onClick={onExpand} title="展开审校" type="button">
        <ChevronLeft aria-hidden="true" size={15} />
      </button>
      <div className="writing-review-rail-score">
        {findings.some(({ finding }) => finding.blocking) ? <ShieldAlert size={16} /> : <ShieldCheck size={16} />}
        <strong>{score == null ? '--' : score.toFixed(2)}</strong>
        <small>质量</small>
      </div>
      <div className="writing-review-rail-status" title={`${findings.length} 条质量 Finding`}>
        <RefreshCw size={14} />
        <strong>{findings.length}</strong>
        <small>Finding</small>
      </div>
      <div className={pendingProposal ? 'writing-review-rail-status pending' : 'writing-review-rail-status'} title={pendingProposal ? '写回提案待决策' : '没有待决策写回提案'}>
        <Database size={14} />
        <strong>{pendingProposal ? '1' : '0'}</strong>
        <small>写回</small>
      </div>
    </aside>
  );
}
