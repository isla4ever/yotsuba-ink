import { BookOpenText, Minimize2, ShieldCheck } from 'lucide-react';
import { useGSAP } from '@gsap/react';
import { gsap } from 'gsap';
import { AnimatePresence } from 'motion/react';
import { useRef, type ReactNode } from 'react';
import { WritingMobileDock } from './WritingMobileDock';
import { WritingMobileSheet } from './WritingMobileSheet';
import { WritingViewModeControl } from './WritingViewModeControl';
import type { WritingViewMode } from './writingViewMode';

gsap.registerPlugin(useGSAP);

export type WritingMobileSheetKey = 'chapter' | 'review' | null;

type Props = {
  busy: boolean;
  chapterLabel: string;
  chapterRail: ReactNode;
  chapterWorkspace: ReactNode;
  compact: boolean;
  contextBar: ReactNode;
  editor: ReactNode;
  mobileSheet: WritingMobileSheetKey;
  onExitFocus: () => void;
  onMobileSheetChange: (sheet: WritingMobileSheetKey) => void;
  onViewModeChange: (mode: WritingViewMode) => void;
  reviewInspector: ReactNode;
  reviewLabel: string;
  reviewRail: ReactNode;
  /** 全书张力心电（10.3c）：Context Bar 下方整行；focus 模式与移动端不渲染。 */
  tensionStrip?: ReactNode;
  viewMode: WritingViewMode;
};

export function WritingWorkbenchLayout({
  busy,
  chapterLabel,
  chapterRail,
  chapterWorkspace,
  compact,
  contextBar,
  editor,
  mobileSheet,
  onExitFocus,
  onMobileSheetChange,
  onViewModeChange,
  reviewInspector,
  reviewLabel,
  reviewRail,
  tensionStrip,
  viewMode,
}: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useGSAP(() => {
    const layout = rootRef.current?.querySelector<HTMLElement>('.writing-stage-layout');
    if (!layout || compact || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    gsap.fromTo(
      layout,
      { autoAlpha: 0.72, y: 2 },
      { autoAlpha: 1, clearProps: 'opacity,transform,visibility', duration: 0.14, ease: 'power2.out', overwrite: 'auto', y: 0 },
    );
  }, { dependencies: [compact, viewMode], revertOnUpdate: true, scope: rootRef });

  if (compact) {
    return (
      <div className="writing-workbench-phase85 writing-workbench-phase95c3 mobile" ref={rootRef}>
        {contextBar}
        <div className="writing-stage-layout writing-mobile-manuscript">{editor}</div>
        <WritingMobileDock
          chapterLabel={chapterLabel}
          onOpenChapter={() => onMobileSheetChange('chapter')}
          onOpenReview={() => onMobileSheetChange('review')}
          reviewLabel={reviewLabel}
        />
        <AnimatePresence>
          {mobileSheet === 'chapter' ? (
            <WritingMobileSheet
              busy={busy}
              icon={BookOpenText}
              key="chapter"
              onClose={() => onMobileSheetChange(null)}
              subtitle={chapterLabel}
              title="章节与上下文"
            >
              {chapterWorkspace}
            </WritingMobileSheet>
          ) : null}
          {mobileSheet === 'review' ? (
            <WritingMobileSheet
              busy={busy}
              icon={ShieldCheck}
              key="review"
              onClose={() => onMobileSheetChange(null)}
              subtitle={reviewLabel}
              title="本章审校"
            >
              {reviewInspector}
            </WritingMobileSheet>
          ) : null}
        </AnimatePresence>
      </div>
    );
  }

  if (viewMode === 'focus') {
    return (
      <div className="writing-workbench-phase85 writing-workbench-phase95c3 focus" ref={rootRef}>
        <div className="writing-stage-layout writing-focus-layout">{editor}</div>
        <button className="writing-focus-exit" onClick={onExitFocus} title="退出专注（Esc）" type="button">
          <Minimize2 size={14} /><span>退出专注</span>
        </button>
      </div>
    );
  }

  return (
    <div className={`writing-workbench-phase85 writing-workbench-phase95c3${tensionStrip ? ' with-tension-strip' : ''}`} ref={rootRef}>
      <div className="writing-workbench-commandbar">
        {contextBar}
        <WritingViewModeControl mode={viewMode} onChange={onViewModeChange} />
      </div>
      {tensionStrip}
      <div className="writing-stage-layout" data-view-mode={viewMode}>
        {viewMode === 'writing' ? chapterWorkspace : chapterRail}
        {editor}
        {viewMode === 'writing' ? reviewRail : reviewInspector}
      </div>
    </div>
  );
}
