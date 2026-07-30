import { CheckCircle2, CircleAlert } from 'lucide-react';
import { detailChapterReadiness, type DetailBaseline } from './detailArtifactModel';
import { detailClueSummary, detailFactSummary, type DetailChapter } from './detailPresentation';

type Props = {
  baseline: DetailBaseline;
  chapters: DetailChapter[];
  deltaBySection: Map<string, string>;
  generating: boolean;
  liveIndex: number;
  onOpenChapter: (index: number) => void;
  selectedChapterIndex: number;
};

export function DetailConstructionTable({ baseline, chapters, deltaBySection, generating, liveIndex, onOpenChapter, selectedChapterIndex }: Props) {
  const chapterNames = chapters.map((chapter) => chapter.chapter);
  return (
    <section aria-label="章节施工表" className="detail-construction-shell detail-construction-phase84">
      <div className="chapter-ledger-table detail-construction-table">
        <div className="detail-construction-scroll">
          <div className="detail-construction-grid">
            <div className="chapter-table-head"><span>章节</span><span>POV / 场景</span><span>目标</span><span>冲突</span><span>事实 / Wiki</span><span>伏笔 / 钩子</span><span>就绪</span></div>
            <div className="chapter-table-body">
              {chapters.map((chapter, index) => {
                const readiness = detailChapterReadiness(chapter, baseline, index, chapterNames);
                const isLive = generating && index === liveIndex;
                return (
                  <button
                    aria-label={`查看${chapter.chapter || `第 ${index + 1} 章`}细纲，完整度 ${readiness.completed}/${readiness.total}`}
                    aria-pressed={selectedChapterIndex === index}
                    className={`chapter-row-card ${selectedChapterIndex === index ? 'active' : ''} ${isLive ? 'generating' : ''}`}
                    key={`${chapter.chapter}-${index}`}
                    onClick={() => onOpenChapter(index)}
                    type="button"
                  >
                    <strong>{chapter.chapter || `第 ${index + 1} 章`}</strong>
                    <span>{chapter.pov || 'POV 待补齐'} · {chapter.scene || '场景待补齐'}</span>
                    <span>{chapter.goal || '章节目标待补齐'}</span>
                    <span>{chapter.conflict || '核心冲突待补齐'}</span>
                    {isLive && deltaBySection.get(chapter.chapter) ? <span className="live-delta-preview">{deltaBySection.get(chapter.chapter)}</span> : <span>{detailFactSummary(chapter)}</span>}
                    <span>{detailClueSummary(chapter)}</span>
                    <em className={readiness.ready ? 'ready' : ''}>{readiness.ready ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}{readiness.completed}/{readiness.total}</em>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
