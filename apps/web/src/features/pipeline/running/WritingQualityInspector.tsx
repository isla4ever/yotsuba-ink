import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  LocateFixed,
  RefreshCw,
  ShieldAlert,
  X,
} from 'lucide-react';
import type { ChapterQualityRepairTarget } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { LoadingButton } from '../layout/LoadingButton';
import type { WritingChapter } from './writingArtifactModel';
import {
  qualityDimensionLabel,
  writingQualityFindings,
  writingQualityScore,
} from './writingReviewModel';

type Props = {
  busy: 'sync' | 'decision' | null;
  chapter: WritingChapter;
  error: string;
  onClearError: () => void;
  onRepair: (target: ChapterQualityRepairTarget) => void;
  onSync: () => void;
  readOnly: boolean;
};

export function WritingQualityInspector({ busy, chapter, error, onClearError, onRepair, onSync, readOnly }: Props) {
  const findings = writingQualityFindings(chapter);
  const score = writingQualityScore(chapter);
  const recheck = chapter.quality_recheck;
  const passed = recheck?.status === 'passed' || Boolean(chapter.writeback_proposal && chapter.writeback_proposal.status !== 'blocked');
  const blocked = recheck?.status === 'blocked' || chapter.writeback_proposal?.status === 'blocked';
  const emptyDetail = chapter.summary_dirty
    ? '同步章节摘要后即可对当前正文执行版本绑定复检。'
    : readOnly
      ? '这份历史正文没有版本绑定复检；新一轮章节定稿时会生成。'
      : '提交当前章节后将生成质量复检与可定位的修订建议。';
  return (
    <section aria-label="质量审校" className="writing-quality-inspector">
      <header className={`writing-review-status${blocked ? ' blocked' : passed ? ' passed' : ''}`}>
        <span>
          {busy === 'sync' ? <ButtonLoadingIndicator /> : blocked ? <ShieldAlert size={15} /> : passed ? <CheckCircle2 size={15} /> : <CircleDashed size={15} />}
          <b>{busy === 'sync' ? '正在复检' : blocked ? '复检未通过' : passed ? '当前版本已通过' : '等待质量复检'}</b>
        </span>
        <strong>{score == null ? '--' : score.toFixed(2)}</strong>
      </header>

      {chapter.summary_dirty ? (
        <div className="writing-review-action-callout">
          <div><RefreshCw size={14} /><span><strong>章节摘要尚未绑定当前正文</strong><small>同步后将使用确定性质量引擎复检，不会重跑正文生成。</small></span></div>
          {!readOnly ? (
            <LoadingButton disabled={Boolean(busy) || !chapter.summary.trim()} loading={busy === 'sync'} loadingLabel="正在复检" onClick={onSync}>
              <RefreshCw size={13} />同步并复检
            </LoadingButton>
          ) : null}
        </div>
      ) : null}

      <div className="writing-finding-heading">
        <span><AlertTriangle size={13} />质量发现</span>
        <b>{findings.length}</b>
      </div>
      <div className="writing-finding-list">
        {findings.map(({ finding, target }) => (
          <article className={`severity-${finding.severity}`} key={finding.id}>
            <div>
              <span>{qualityDimensionLabel(finding.dimension)}</span>
              <small>{finding.blocking ? '需人工处理' : finding.severity === 'warning' ? '建议修订' : '提示'}</small>
            </div>
            <strong>{finding.message}</strong>
            {finding.evidence ? <p>证据：{finding.evidence}</p> : null}
            {target ? (
              <div className="writing-finding-resolution">
                <p>修订方向：{target.instruction}</p>
                {!readOnly && target.locatable ? (
                  <button onClick={() => onRepair(target)} type="button"><LocateFixed size={12} />定位正文</button>
                ) : <small>{target.locatable ? '当前阶段已定稿' : '无法可靠定位，仅提供修订方向'}</small>}
              </div>
            ) : (
              <div className="writing-finding-resolution">
                <p>修订方向：{finding.target || '结合证据手动调整对应段落'}</p>
                <small>无法可靠定位，仅提供修订方向</small>
              </div>
            )}
          </article>
        ))}
        {!findings.length ? (
          <div className="writing-review-empty">
            {passed ? <CheckCircle2 size={18} /> : <CircleDashed size={18} />}
            <strong>{passed ? '未发现需要处理的质量问题' : '本章尚无复检结果'}</strong>
            <span>{passed ? '连续性、结构与约束检查已经闭合。' : emptyDetail}</span>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="writing-review-error" role="alert">
          <span>{error}</span><button aria-label="关闭复检错误" onClick={onClearError} type="button"><X size={12} /></button>
        </div>
      ) : null}
    </section>
  );
}
