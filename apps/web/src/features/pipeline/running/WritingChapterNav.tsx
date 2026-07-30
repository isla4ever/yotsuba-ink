import { CheckCircle2, CircleDashed } from 'lucide-react';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import type { WritingChapter } from './writingArtifactModel';

type Props = {
  activeChapterId: string;
  chapters: WritingChapter[];
  compact?: boolean;
  locked?: boolean;
  onSelect: (chapterId: string) => void;
};

export function WritingChapterNav({ activeChapterId, chapters, compact = false, locked = false, onSelect }: Props) {
  return (
    <nav aria-label="正文章节" className={`writing-chapter-nav${compact ? ' compact' : ''}`}>
      <div className="writing-rail-heading">
        <span>章节</span>
        <small>{locked ? '处理中' : `${chapters.filter((chapter) => chapter.status === 'completed').length}/${chapters.length}`}</small>
      </div>
      <div className="writing-chapter-list">
        {chapters.map((chapter, index) => {
          const StatusIcon = chapter.status === 'completed' ? CheckCircle2 : CircleDashed;
          return (
            <button
              aria-current={activeChapterId === chapter.id ? 'page' : undefined}
              className={`${chapter.status}${activeChapterId === chapter.id ? ' active' : ''}`}
              disabled={locked && activeChapterId !== chapter.id}
              key={chapter.id}
              onClick={() => onSelect(chapter.id)}
              title={locked ? '当前操作完成后可切换章节' : chapter.title}
              type="button"
            >
              {chapter.status === 'committing' ? <ButtonLoadingIndicator /> : <StatusIcon aria-hidden="true" size={14} />}
              <span>
                <strong>{compact ? index + 1 : chapter.title}</strong>
                {compact ? null : <small>{chapter.words.toLocaleString()} 字 · v{chapter.version}</small>}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
