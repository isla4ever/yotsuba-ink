import { Database, Link2, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { QualityMode, RunEvent } from '../../contracts';
import { backdropMotionVariants, sheetMotionVariants } from '../../lib/motion';
import { runEventLabel } from '../../lib/runEventLabels';
import { useOverlayDialog } from '../../state/useOverlayDialog';
import type { ChapterReviewInsight } from '../writingArtifactModel';

type Props = {
  embeddedDetail?: boolean;
  events: RunEvent[];
  qualityMode?: QualityMode;
  stageEnrichment?: { label: string; detail: string };
  chapterReview?: ChapterReviewInsight;
};

export function WikiMemoryPanel({ chapterReview, embeddedDetail, events, qualityMode = 'balanced', stageEnrichment }: Props) {
  const [detailOpen, setDetailOpen] = useState(false);
  const detailRef = useOverlayDialog<HTMLElement>({ onClose: () => setDetailOpen(false), open: detailOpen });
  const reads = events.filter((event) => event.type === 'memory_context_loaded');
  const writes = events.filter((event) => event.type === 'memory_writeback_completed');
  const canonEvents = events.filter((event) => event.type === 'canon_facts_committed');
  const canonFacts = canonEvents.flatMap((event) => event.committed ?? []);
  const pendingConflicts = canonEvents.flatMap((event) => event.pending_conflicts ?? []);
  const hits = wikiConstraintKinds([...reads, ...writes]);
  const detail = (
    <WikiMemoryDetail
      hits={hits}
      chapterReview={chapterReview}
      canonEvents={canonEvents}
      reads={reads}
      writes={writes}
      onClose={() => setDetailOpen(false)}
      showClose={!embeddedDetail}
    />
  );
  return (
    <section className="config-section runtime-insight-card compact-widget wiki-memory-widget">
      <button className="widget-open-button" onClick={() => !embeddedDetail && setDetailOpen(true)} type="button">
        <span><Database size={16} />Wiki 事实层</span>
        <b>{canonFacts.length || hits.length}</b>
      </button>
      {embeddedDetail ? detail : (
        <>
      <div className="widget-kpis">
        <span><strong>{reads.length}</strong>读取</span>
        <span><strong>{writes.length}</strong>写回</span>
        <span><strong>{canonFacts.length}</strong>正典事实</span>
      </div>
      <div className="chip-grid compact">
        {hits.slice(0, 4).map((hit) => <span key={hit}>{hit}</span>)}
      </div>
      {stageEnrichment ? (
        <div className="insight-stage-enrichment wiki">
          <strong>{stageEnrichment.label}</strong>
          <span>{stageEnrichment.detail}</span>
        </div>
      ) : null}
      {chapterReview?.proposal ? (
        <div className="insight-stage-enrichment wiki chapter-proposal-enrichment">
          <strong>{chapterReview.chapter}写回提案</strong>
          <span>{proposalSummary(chapterReview)}</span>
        </div>
      ) : null}
      {pendingConflicts.length ? <p className="wiki-conflict-warning">{pendingConflicts.length} 条正典冲突等待处理，既有事实保持不变。</p> : null}
      <p>{reads.length || writes.length || canonFacts.length ? '事实账本已跟随当前阶段同步。' : '运行后显示当前阶段读写记录。'}</p>
        </>
      )}
      {createPortal(
        <AnimatePresence>
          {detailOpen ? (
            <motion.div animate="animate" className={`runtime-side-detail-backdrop app-overlay-backdrop wiki-side-backdrop mode-${qualityMode}`} exit="exit" initial="initial" role="presentation" onClick={() => setDetailOpen(false)} variants={backdropMotionVariants}>
              <motion.aside
                animate="animate"
                aria-label="Wiki 事实层详情"
                aria-modal="true"
                className={`runtime-side-detail-sheet app-sheet-surface wiki-memory-side-detail mode-${qualityMode}`}
                exit="exit"
                initial="initial"
                onClick={(event) => event.stopPropagation()}
                ref={detailRef}
                role="dialog"
                tabIndex={-1}
                variants={sheetMotionVariants}
              >
                {detail}
              </motion.aside>
            </motion.div>
          ) : null}
        </AnimatePresence>,
        document.body,
      )}
    </section>
  );
}

function wikiConstraintKinds(events: RunEvent[]) {
  const kinds = events.flatMap((event) => {
    const memoryKinds = Array.isArray(event.memory?.constraint_kinds) ? event.memory.constraint_kinds : [];
    const writtenKinds = event.written?.map((item) => item.kind || item.type || item.target) ?? [];
    return [...memoryKinds, ...writtenKinds].map((item) => String(item ?? '').trim()).filter(Boolean);
  });
  return Array.from(new Set(kinds)).slice(0, 8);
}

function WikiMemoryDetail({
  hits,
  onClose,
  reads,
  showClose,
  writes,
  chapterReview,
  canonEvents,
}: {
  hits: string[];
  onClose: () => void;
  reads: RunEvent[];
  showClose: boolean;
  writes: RunEvent[];
  chapterReview?: ChapterReviewInsight;
  canonEvents: RunEvent[];
}) {
  return (
    <section className="wiki-memory-detail">
      {showClose ? <button aria-label="关闭详情" className="modal-close" onClick={onClose} type="button"><X size={20} /></button> : null}
      <p className="eyebrow">事实记忆</p>
      <h2><Link2 size={18} />约束命中与写回</h2>
      <div className="wiki-detail-summary">
        <span><strong>{reads.length}</strong>读取</span>
        <span><strong>{writes.length}</strong>写回</span>
        <span><strong>{canonEvents.flatMap((event) => event.committed ?? []).length}</strong>正典事实</span>
      </div>
      <div className="chip-grid wiki-detail-chips">
        {hits.map((hit) => <span key={hit}>{hit}</span>)}
      </div>
      <div className="field-list expanded wiki-memory-event-list">
        {chapterReview?.proposal ? (
          <article className="wiki-proposal-event">
            <strong>{chapterReview.chapter} · {proposalStatus(chapterReview.proposal.status)}</strong>
            <span>{proposalSummary(chapterReview)}</span>
            <small>{runEventLabel('chapter_writeback_proposal_generated')}</small>
          </article>
        ) : null}
        {canonEvents.slice(0, 8).map((event, index) => (
          <article key={`canon-${event.chapter}-${index}`}>
            <strong>{event.chapter} · 写入正典</strong>
            <span>新增 {event.committed?.length ?? 0} · 冲突处理 {event.resolved?.length ?? 0}</span>
            <small>{runEventLabel('canon_facts_committed')}</small>
          </article>
        ))}
        {[...reads, ...writes].slice(0, 12).map((event, index) => (
          <article key={`${event.type}-${event.node_id}-${index}`}>
            <strong>{event.type === 'memory_context_loaded' ? '读取约束' : '写回记忆'}</strong>
            <span>{event.label ?? event.node_id}</span>
            <small>{runEventLabel(event.type)}</small>
          </article>
        ))}
        {!reads.length && !writes.length && !canonEvents.length ? <p className="muted">运行后可以看到每个阶段读取和写入了哪些设定。</p> : null}
      </div>
    </section>
  );
}

function proposalSummary(review: ChapterReviewInsight) {
  const counts = review.proposal?.counts;
  if (!counts) return '等待章节复检生成写回提案';
  const conflicts = review.proposal?.canon?.conflicts?.filter((item) => item.status === 'pending').length ?? 0;
  return `Wiki ${counts.wiki} · 人物 ${counts.character} · 伏笔 ${counts.foreshadow}${conflicts ? ` · 冲突 ${conflicts}` : ''}`;
}

function proposalStatus(status: NonNullable<ChapterReviewInsight['proposal']>['status']) {
  return {
    pending: '待决策',
    accepted: '已采纳，待定稿写回',
    rejected: '已拒绝',
    blocked: '复检未通过',
    not_required: '无需写回',
  }[status];
}
