import { Check, FileCheck2, GitBranch, ShieldAlert, UsersRound, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { ChapterWritebackProposal } from '../contracts';
import { LoadingButton } from '../layout/LoadingButton';
import type { WritingChapter } from './writingArtifactModel';
import { proposalStatusText, writingProposalEntries } from './writingReviewModel';

type Props = {
  busy: 'sync' | 'decision' | null;
  chapter: WritingChapter;
  error: string;
  onClearError: () => void;
  onDecide: (
    proposal: ChapterWritebackProposal,
    decision: 'accepted' | 'rejected',
    conflictResolutions: NonNullable<ChapterWritebackProposal['conflict_resolutions']>,
  ) => void;
  readOnly: boolean;
};

export function WritingWritebackInspector({ busy, chapter, error, onClearError, onDecide, readOnly }: Props) {
  const proposal = chapter.writeback_proposal;
  const entries = writingProposalEntries(proposal);
  const conflicts = proposal?.canon?.conflicts?.filter((item) => item.status === 'pending') ?? [];
  const [resolutions, setResolutions] = useState<NonNullable<ChapterWritebackProposal['conflict_resolutions']>>({});
  useEffect(() => setResolutions(proposal?.conflict_resolutions ?? {}), [proposal?.id]);
  const conflictsReady = conflicts.every((item) => resolutions[item.id]);

  if (!proposal) {
    return (
      <section aria-label="事实写回" className="writing-writeback-inspector">
        <div className="writing-review-empty writing-writeback-empty">
          <FileCheck2 size={18} />
          <strong>等待质量复检生成写回提案</strong>
          <span>Wiki、人物变化和伏笔只会形成版本绑定的提案，不会在本页自动写入正典。</span>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="事实写回" className={`writing-writeback-inspector status-${proposal.status}`}>
      <header className="writing-writeback-head">
        <span><FileCheck2 size={15} /><b>本章写回提案</b></span>
        <strong>{proposalStatusText(proposal.status)}</strong>
      </header>
      <div className="writing-proposal-counts" aria-label="写回提案规模">
        <span><FileCheck2 size={12} /><b>{proposal.counts.wiki}</b>Wiki</span>
        <span><UsersRound size={12} /><b>{proposal.counts.character}</b>人物</span>
        <span><GitBranch size={12} /><b>{proposal.counts.foreshadow}</b>伏笔</span>
      </div>

      <div className="writing-proposal-list">
        {entries.map((entry) => (
          <article className={`kind-${entry.kind}`} key={entry.id}>
            <span>{entry.kind === 'wiki' ? 'Wiki 事实' : entry.kind === 'character' ? '人物变化' : '伏笔状态'}</span>
            <strong>{entry.label}</strong>
            <p>{entry.detail}</p>
            <small>{entry.meta}</small>
          </article>
        ))}
        {!entries.length ? <p className="writing-proposal-none">当前版本没有需要写入 Wiki、人物关系或伏笔账本的变化。</p> : null}
      </div>

      {conflicts.length ? (
        <section className="writing-canon-conflicts">
          <header><span><ShieldAlert size={13} />正典冲突</span><b>{conflicts.length}</b></header>
          {conflicts.map((conflict) => (
            <article key={conflict.id}>
              <div><strong>{conflict.target}</strong><span>{conflict.claim_key}</span></div>
              <p><small>既有事实</small>{conflict.existing_fact}</p>
              <p><small>本章提案</small>{conflict.incoming_fact}</p>
              <div className="writing-conflict-actions">
                <button aria-pressed={resolutions[conflict.id] === 'keep_existing'} disabled={readOnly || Boolean(busy)} onClick={() => setResolutions((current) => ({ ...current, [conflict.id]: 'keep_existing' }))} type="button">保留既有</button>
                <button aria-pressed={resolutions[conflict.id] === 'replace_existing'} disabled={readOnly || Boolean(busy)} onClick={() => setResolutions((current) => ({ ...current, [conflict.id]: 'replace_existing' }))} type="button">采用新事实</button>
              </div>
            </article>
          ))}
        </section>
      ) : null}

      {!readOnly && proposal.status === 'pending' ? (
        <footer className="writing-proposal-actions">
          <button disabled={Boolean(busy)} onClick={() => onDecide(proposal, 'rejected', {})} type="button"><X size={13} />拒绝提案</button>
          <LoadingButton className="accept" disabled={Boolean(busy) || !conflictsReady} loading={busy === 'decision'} loadingLabel="正在写回" onClick={() => onDecide(proposal, 'accepted', resolutions)}>
            <Check size={13} />接受提案
          </LoadingButton>
        </footer>
      ) : null}

      {error ? (
        <div className="writing-review-error" role="alert">
          <span>{error}</span><button aria-label="关闭提案错误" onClick={onClearError} type="button"><X size={12} /></button>
        </div>
      ) : null}
    </section>
  );
}
