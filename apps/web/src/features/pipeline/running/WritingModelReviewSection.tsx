import { AudioLines, BotMessageSquare, CircleOff } from 'lucide-react';
import { modelReviewUnavailableText } from './modelReviewPresentation';
import type { WritingChapter } from './writingArtifactModel';

type Props = {
  chapter: WritingChapter;
};

/**
 * Deep/balanced 档「模型评审」分区（Phase 10.3c，质量审校 Tab 内、L1 结果上方）。
 * 只做展示与既有入口联动：维度条形为真实 0-10 分（单一 sequential 色相，dataviz 规范）；
 * 修订指令通过既有「选区 → 生成候选」链路执行，不新增生成链路。
 * status=unavailable 如实显示评审不可用原因；无 model_review（旧 Run）显示紧凑缺失态。
 * fast 档由父组件整段不渲染（无禁用壳）。
 */
export function WritingModelReviewSection({ chapter }: Props) {
  const review = chapter.model_review;
  if (!review) return null;
  if (review.status === 'unavailable') {
    return (
      <div className="model-review-unavailable" role="status">
        <span><CircleOff size={14} /><strong>本章模型评审不可用</strong></span>
        <p>{modelReviewUnavailableText(review.error ?? '')}</p>
        {review.error ? <small>原始原因：{review.error}</small> : null}
      </div>
    );
  }
  const dimensions = review.dimensions ?? [];
  const versionNote = (review.chapter_version ?? 0) > 0 && review.chapter_version !== chapter.version
    ? `评审基于 v${review.chapter_version}，当前正文已更新至 v${chapter.version}`
    : `评审对象：v${review.chapter_version || chapter.version}`;
  return (
    <section aria-label="模型评审报告" className="model-review-section signature-chart">
      <header className="model-review-head">
        <span><BotMessageSquare size={14} />模型评审</span>
        <strong aria-label={`综合评分 ${Number(review.overall_score ?? 0).toFixed(1)} / 10`}>
          {Number(review.overall_score ?? 0).toFixed(1)}<small>/10</small>
        </strong>
      </header>
      <small className="model-review-version">{versionNote}</small>
      <ul className="model-review-dimensions">
        {dimensions.map((dimension, index) => (
          <li key={`${dimension.dimension}-${index}`}>
            <div className="model-review-dimension-row">
              <span>{dimension.dimension}</span>
              <b>{dimension.score.toFixed(1)}</b>
            </div>
            <div aria-hidden="true" className="model-review-bar">
              <i style={{ width: `${(dimension.score / 10) * 100}%` }} />
            </div>
            {dimension.evidence ? <p className="model-review-evidence">证据：{dimension.evidence}</p> : null}
            {dimension.revision_instruction ? (
              <p className="model-review-instruction">
                修订指令：{dimension.revision_instruction}
                <small>在正文中选中相应段落，用「生成修订候选」执行此指令。</small>
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {review.voice?.drift ? (
        <div className="model-review-voice-drift" role="status">
          <span><AudioLines size={13} /><strong>检测到语声漂移</strong></span>
          {review.voice.notes ? <p>{review.voice.notes}</p> : <p>本章叙事语声与 Voice Spec 基准出现偏移，建议对照语声表复核。</p>}
        </div>
      ) : null}
    </section>
  );
}
