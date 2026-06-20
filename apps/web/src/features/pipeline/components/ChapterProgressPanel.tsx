import { BookOpenText } from 'lucide-react';
import type { ChapterProgressItem, RunEvent } from '../types/workflow';

type Props = {
  events: RunEvent[];
};

const fallback: ChapterProgressItem[] = [
  { volume: '第一卷', chapter: '第1章', status: 'completed', words: 2460, quality_score: 0.86, node_id: 'text' },
  { volume: '第一卷', chapter: '第2章', status: 'completed', words: 2310, quality_score: 0.84, node_id: 'text' },
  { volume: '第一卷', chapter: '第3章', status: 'running', words: 980, quality_score: 0.0, node_id: 'text' },
  { volume: '第一卷', chapter: '第4章', status: 'planned', words: 0, quality_score: 0.0, node_id: 'text' },
  { volume: '第一卷', chapter: '第5章', status: 'planned', words: 0, quality_score: 0.0, node_id: 'text' },
  { volume: '第一卷', chapter: '第6章', status: 'planned', words: 0, quality_score: 0.0, node_id: 'text' },
];

export function ChapterProgressPanel({ events }: Props) {
  const latest = events.find((event) => event.type === 'chapter_progress_updated' && event.chapters);
  const chapters = latest?.chapters?.length ? latest.chapters : fallback;
  const completed = chapters.filter((chapter) => chapter.status === 'completed').length;
  const words = chapters.reduce((sum, chapter) => sum + chapter.words, 0);
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><BookOpenText size={16} />正文进度</h3>
        <div className="stats-grid">
          <strong>{completed}/{chapters.length}<span>章节</span></strong>
          <strong>{words.toLocaleString()}<span>字数</span></strong>
          <strong>{Math.round((completed / chapters.length) * 100)}%<span>完成度</span></strong>
        </div>
      </section>
      <section className="config-section">
        <h3>卷/章生成状态</h3>
        <div className="chapter-grid">
          {chapters.map((chapter) => (
            <article className={chapter.status} key={chapter.chapter}>
              <strong>{chapter.chapter}</strong>
              <span>{chapter.volume}</span>
              <small>{chapter.status} · {chapter.words} 字 · Q {chapter.quality_score ? chapter.quality_score.toFixed(2) : '-'}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
