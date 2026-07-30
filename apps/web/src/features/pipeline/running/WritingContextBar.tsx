import { BookOpenText, Boxes, FileCheck2, ScrollText, ShieldCheck } from 'lucide-react';
import type { ParallelDeliverySnapshot } from './parallelDeliveryModel';
import type { WritingArtifact, WritingChapter, WritingReadiness } from './writingArtifactModel';
import { chapterOutlinePresentation, type DetailChapterContext } from './writingContextPresentation';

type Props = {
  artifact: WritingArtifact;
  chapter: WritingChapter;
  detailChapter?: DetailChapterContext;
  readiness: WritingReadiness;
  streaming: boolean;
  delivery: ParallelDeliverySnapshot;
  onOpenDelivery: () => void;
  readOnly: boolean;
};

export function WritingContextBar({ artifact, chapter, delivery, detailChapter, onOpenDelivery, readOnly, readiness, streaming }: Props) {
  const chapterIndex = Math.max(0, artifact.chapters.findIndex((item) => item.id === chapter.id));
  const totalWords = artifact.chapters.reduce((total, item) => total + item.words, 0);
  const proposalImpliesPassedReview = Boolean(chapter.writeback_proposal && chapter.writeback_proposal.status !== 'blocked');
  const reviewLabel = chapter.summary_dirty
    ? '摘要待同步'
    : chapter.quality_recheck?.status === 'blocked'
      ? '质量待修复'
      : chapter.quality_recheck?.status === 'passed' || proposalImpliesPassedReview
        ? '复检通过'
        : '等待复检';
  const proposalLabel = chapter.writeback_proposal?.status === 'pending'
    ? '写回待决策'
    : chapter.writeback_proposal?.status === 'accepted'
      ? '写回已采纳'
      : chapter.writeback_proposal?.status === 'rejected'
        ? '写回已拒绝'
        : '暂无写回提案';
  const percentage = readiness.total
    ? Math.round((readiness.completed / readiness.total) * 100)
    : 0;
  const recoveredContext = readOnly && !chapter.context_packet?.chapter_outline?.trim() && Boolean(detailChapter);

  return (
    <section aria-label="正文写作上下文" className="writing-context-bar-phase85">
      <div className="writing-context-title-phase85">
        <span><BookOpenText size={13} />正文施工</span>
        <strong>第 {chapterIndex + 1}/{artifact.target_chapters} 章 · {chapter.generated_title || chapter.title}</strong>
        <small>{chapterOutlinePresentation(chapter.context_packet, detailChapter)}</small>
      </div>
      <div aria-label="当前正文状态" className="writing-context-metrics-phase85">
        <span><ScrollText size={12} /><b>{totalWords.toLocaleString()}</b> 总字数</span>
        <span><ShieldCheck size={12} />{streaming ? '正在生成' : reviewLabel}</span>
        <span><FileCheck2 size={12} />{proposalLabel}</span>
        <button className={`writing-parallel-entry is-${delivery.status}`} onClick={onOpenDelivery} type="button"><Boxes size={12} /><span>并行交付</span><b>{delivery.coverReady}/{delivery.coverTotal || '—'}</b></button>
      </div>
      <div aria-label={`章节完成度 ${readiness.completed}/${readiness.total}`} className={`writing-readiness-phase85${readiness.ready ? ' ready' : ''}`} role="status">
        <div><span>章节完成</span><strong>{readiness.completed}/{readiness.total}</strong></div>
        <i aria-hidden="true"><b style={{ width: `${percentage}%` }} /></i>
        <small>{streaming ? '正文写入中' : readiness.ready ? '可进入阶段定稿' : recoveredContext ? '历史正文已完成 · 细纲上下文已回溯显示' : `待处理：${readiness.missingLabels[0] || '章节必填内容'}`}</small>
      </div>
    </section>
  );
}
