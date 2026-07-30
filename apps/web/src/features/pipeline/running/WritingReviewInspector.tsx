import { BookOpenCheck, Database, Globe2, Network, ShieldCheck } from 'lucide-react';
import { useGSAP } from '@gsap/react';
import { gsap } from 'gsap';
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import type { ChapterQualityRepairTarget, ChapterWritebackProposal, QualityMode, RunEvent } from '../contracts';
import { showModelReviewSection } from './modelReviewPresentation';
import type { WritingChapter } from './writingArtifactModel';
import { writingReviewDefaultTab, writingReviewSteps } from './writingReviewModel';
import { WritingModelReviewSection } from './WritingModelReviewSection';
import { WritingQualityInspector } from './WritingQualityInspector';
import { WritingWritebackInspector } from './WritingWritebackInspector';

gsap.registerPlugin(useGSAP);

type ReviewTab = 'quality' | 'writeback';

type Props = {
  busy: 'sync' | 'decision' | null;
  chapter: WritingChapter;
  error: string;
  events: RunEvent[];
  onClearError: () => void;
  onDecide: (
    proposal: ChapterWritebackProposal,
    decision: 'accepted' | 'rejected',
    conflictResolutions: NonNullable<ChapterWritebackProposal['conflict_resolutions']>,
  ) => void;
  onOpenCharacter: () => void;
  onOpenWorldbuilding: () => void;
  onRepair: (target: ChapterQualityRepairTarget) => void;
  onSync: () => void;
  panelIdPrefix?: string;
  qualityMode: QualityMode;
  readOnly: boolean;
};

export function WritingReviewInspector({
  busy,
  chapter,
  error,
  events,
  onClearError,
  onDecide,
  onOpenCharacter,
  onOpenWorldbuilding,
  onRepair,
  onSync,
  panelIdPrefix = 'writing-review',
  qualityMode,
  readOnly,
}: Props) {
  const [tab, setTab] = useState<ReviewTab>(() => writingReviewDefaultTab(chapter));
  const inspectorRef = useRef<HTMLElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const qualityTabRef = useRef<HTMLButtonElement>(null);
  const writebackTabRef = useRef<HTMLButtonElement>(null);
  useEffect(() => setTab(writingReviewDefaultTab(chapter)), [chapter.id]);
  useGSAP(() => {
    const panel = panelRef.current;
    if (!panel || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    gsap.fromTo(
      panel.children,
      { autoAlpha: 0, x: 3 },
      {
        autoAlpha: 1,
        clearProps: 'opacity,transform,visibility',
        duration: 0.15,
        ease: 'power2.out',
        overwrite: 'auto',
        stagger: 0.015,
        x: 0,
      },
    );
  }, { dependencies: [chapter.id, tab], revertOnUpdate: true, scope: inspectorRef });
  const steps = writingReviewSteps(chapter);
  const committedFacts = events
    .filter((event) => event.type === 'canon_facts_committed')
    .flatMap((event) => event.committed ?? []).length;
  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const next = ['ArrowLeft', 'ArrowUp', 'Home'].includes(event.key)
      ? 'quality'
      : ['ArrowRight', 'ArrowDown', 'End'].includes(event.key)
        ? 'writeback'
        : null;
    if (!next) return;
    event.preventDefault();
    setTab(next);
    (next === 'quality' ? qualityTabRef : writebackTabRef).current?.focus();
  };
  return (
    <aside aria-label="正文审校 Inspector" className="writing-review-inspector" ref={inspectorRef}>
      <header className="writing-review-inspector-head">
        <div><span><BookOpenCheck size={14} />本章审校</span><strong>{chapter.generated_title || chapter.title}</strong></div>
        <small>v{chapter.version} · 正典 {committedFacts}</small>
      </header>

      <ol aria-label="本章审校流程" className="writing-review-steps">
        {steps.map((step) => <li className={step.state} key={step.id}><i />{step.label}</li>)}
      </ol>

      <div aria-label="审校视图" className="writing-review-tabs" role="tablist">
        <button aria-controls={`${panelIdPrefix}-quality-panel`} aria-selected={tab === 'quality'} id={`${panelIdPrefix}-quality-tab`} onClick={() => setTab('quality')} onKeyDown={handleTabKeyDown} ref={qualityTabRef} role="tab" tabIndex={tab === 'quality' ? 0 : -1} type="button">
          <ShieldCheck size={13} />质量审校
        </button>
        <button aria-controls={`${panelIdPrefix}-writeback-panel`} aria-selected={tab === 'writeback'} id={`${panelIdPrefix}-writeback-tab`} onClick={() => setTab('writeback')} onKeyDown={handleTabKeyDown} ref={writebackTabRef} role="tab" tabIndex={tab === 'writeback' ? 0 : -1} type="button">
          <Database size={13} />事实写回
          {chapter.writeback_proposal?.status === 'pending' ? <b>待决策</b> : null}
        </button>
      </div>

      <div className="writing-review-panel" id={`${panelIdPrefix}-${tab}-panel`} ref={panelRef} role="tabpanel" aria-labelledby={`${panelIdPrefix}-${tab}-tab`}>
        {tab === 'quality' ? (
          <>
            {showModelReviewSection(qualityMode) ? <WritingModelReviewSection chapter={chapter} /> : null}
            <WritingQualityInspector
              busy={busy}
              chapter={chapter}
              error={error}
              onClearError={onClearError}
              onRepair={onRepair}
              onSync={onSync}
              readOnly={readOnly}
            />
          </>
        ) : (
          <WritingWritebackInspector
            busy={busy}
            chapter={chapter}
            error={error}
            onClearError={onClearError}
            onDecide={onDecide}
            readOnly={readOnly}
          />
        )}
      </div>

      <footer className="writing-review-related">
        <button onClick={onOpenCharacter} type="button"><Network size={13} /><span><strong>人物关系</strong><small>查看定稿影响</small></span></button>
        <button onClick={onOpenWorldbuilding} type="button"><Globe2 size={13} /><span><strong>世界观</strong><small>查看事实锚点</small></span></button>
      </footer>
    </aside>
  );
}
