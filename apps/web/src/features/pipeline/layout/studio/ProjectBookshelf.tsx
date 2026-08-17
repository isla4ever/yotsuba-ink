import { ArrowRight, BookOpen, ChevronLeft, ChevronRight } from 'lucide-react';
import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { ButtonLoadingIndicator } from '../ButtonLoadingIndicator';
import { ManuscriptLoadingIndicator } from '../ManuscriptLoadingIndicator';
import {
  formatWordCount,
  relativeTimeLabel,
  runStatusLabel,
  stageProgressDots,
} from './studioModel';

type Props = {
  projects: ProjectRecord[];
  summaries: Record<string, ProjectSummary>;
  loading: boolean;
  error: string;
  onOpen: (project: ProjectRecord, summary: ProjectSummary | null) => void;
  openingProjectId?: string;
};

/**
 * Works library as a bookshelf: standing book spines on the left (one per
 * project, vertical titles), a reading-desk detail panel on the right for the
 * selected work. Single click selects, the desk's CTA (or double click) opens.
 */
export function ProjectBookshelf({ projects, summaries, loading, error, onOpen, openingProjectId = '' }: Props) {
  const [selectedId, setSelectedId] = useState('');
  const [scrollState, setScrollState] = useState({ next: false, prev: false });
  const shelfRef = useRef<HTMLDivElement>(null);
  const selected = projects.find((project) => project.id === selectedId) ?? projects[0] ?? null;

  useEffect(() => {
    if (selected && selected.id !== selectedId) setSelectedId(selected.id);
  }, [selected, selectedId]);

  const syncScrollState = useCallback(() => {
    const rail = shelfRef.current;
    if (!rail) return;
    setScrollState({
      next: rail.scrollLeft + rail.clientWidth < rail.scrollWidth - 2,
      prev: rail.scrollLeft > 2,
    });
  }, []);

  useEffect(() => {
    const rail = shelfRef.current;
    if (!rail) return undefined;
    syncScrollState();
    rail.addEventListener('scroll', syncScrollState, { passive: true });
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(syncScrollState);
    observer?.observe(rail);
    window.addEventListener('resize', syncScrollState);
    return () => {
      rail.removeEventListener('scroll', syncScrollState);
      observer?.disconnect();
      window.removeEventListener('resize', syncScrollState);
    };
  }, [projects.length, syncScrollState]);

  if (loading && !projects.length && !error) {
    return (
      <div className="studio-loading-state" role="status">
        <ManuscriptLoadingIndicator />
        <strong>正在同步作品库</strong>
        <span>读取作品、运行摘要与模板状态</span>
      </div>
    );
  }
  if (!loading && !error && projects.length === 0) {
    return (
      <div className="studio-empty-state">
        <h2>书架还空着</h2>
        <p>从上方新建第一部作品，它会以一本书的形式立在这里。</p>
      </div>
    );
  }

  const summary = selected ? summaries[selected.id] ?? null : null;
  const scrollShelf = (direction: -1 | 1) => {
    shelfRef.current?.scrollBy({ behavior: 'smooth', left: direction * Math.max(shelfRef.current.clientWidth * 0.72, 260) });
  };

  return (
    <>
      {error ? <p className="studio-inline-error" role="alert">{error}</p> : null}
      <div className="studio-bookshelf-layout">
        <div className="studio-shelf-frame">
          <button aria-controls="project-shelf-rail" aria-label="向左浏览作品" className="studio-shelf-control prev" disabled={!scrollState.prev} onClick={() => scrollShelf(-1)} title="向左浏览作品" type="button">
            <ChevronLeft aria-hidden="true" size={18} />
          </button>
          <div aria-label="书架" className="studio-shelf" id="project-shelf-rail" ref={shelfRef} role="listbox">
            {projects.map((project) => {
              const projectSummary = summaries[project.id] ?? null;
              const active = selected?.id === project.id;
              return (
                <button
                  aria-selected={active}
                  className={`studio-book-spine${active ? ' selected' : ''}`}
                  key={project.id}
                  onClick={() => setSelectedId(project.id)}
                  onDoubleClick={() => onOpen(project, projectSummary)}
                  role="option"
                  style={{ '--project-accent-hue': project.accent_hue } as CSSProperties}
                  title={`${project.title} · ${formatWordCount(projectSummary?.words ?? 0)}`}
                  type="button"
                >
                  <span className="spine-band" aria-hidden="true" />
                  <span className="spine-title">{project.title}</span>
                  <span className="spine-words">{formatWordCount(projectSummary?.words ?? 0)}</span>
                </button>
              );
            })}
            <span aria-hidden="true" className="studio-shelf-board" />
          </div>
          <button aria-controls="project-shelf-rail" aria-label="向右浏览作品" className="studio-shelf-control next" disabled={!scrollState.next} onClick={() => scrollShelf(1)} title="向右浏览作品" type="button">
            <ChevronRight aria-hidden="true" size={18} />
          </button>
        </div>

        {selected ? (
          <BookDesk
            onOpen={() => onOpen(selected, summary)}
            opening={openingProjectId === selected.id}
            project={selected}
            summary={summary}
          />
        ) : null}
      </div>
    </>
  );
}

function BookDesk({
  onOpen,
  opening,
  project,
  summary,
}: {
  onOpen: () => void;
  opening: boolean;
  project: ProjectRecord;
  summary: ProjectSummary | null;
}) {
  const dots = stageProgressDots(summary);
  const doneCount = dots.filter((dot) => dot.status === 'completed').length;
  const runStatus = runStatusLabel(summary?.status ?? '');
  const updatedAt = summary?.updated_at || project.updated_at;
  return (
    <aside aria-label="作品详情" className="studio-book-desk" style={{ '--project-accent-hue': project.accent_hue } as CSSProperties}>
      <div className="desk-cover" aria-hidden="true">
        <span className="desk-cover-title">{project.title}</span>
        <span className="desk-cover-rule" />
      </div>
      <div className="desk-body">
        <header className="desk-head">
          <h2>{project.title}</h2>
          <span className={`studio-card-status ${project.status}`}>
            {project.status === 'archived' ? '已归档' : runStatus || '创作中'}
          </span>
        </header>
        <p className="desk-summary">{project.summary || summary?.latest_run?.summary || '尚未填写概要。'}</p>
        <dl className="desk-metrics">
          <div><dt>累计字数</dt><dd>{formatWordCount(summary?.words ?? 0)}</dd></div>
          <div><dt>阶段进度</dt><dd>{doneCount}/{dots.length}</dd></div>
          <div><dt>最近更新</dt><dd>{relativeTimeLabel(updatedAt)}</dd></div>
        </dl>
        <ol aria-label="八阶段进度" className="desk-stage-list">
          {dots.map((dot) => (
            <li className={`desk-stage-row ${dot.status}`} key={dot.id}>
              <span aria-hidden="true" className={`studio-progress-dot ${dot.status}`} />
              <span className="desk-stage-label">{dot.label}</span>
              <span className="desk-stage-state">{stageStateLabel(dot.status)}</span>
            </li>
          ))}
        </ol>
        <button
          aria-busy={opening || undefined}
          className="tech-button desk-open-button"
          disabled={opening}
          onClick={onOpen}
          type="button"
        >
          {opening ? <><ButtonLoadingIndicator />正在打开</> : <><BookOpen aria-hidden="true" size={16} />打开这本书<ArrowRight aria-hidden="true" size={14} /></>}
        </button>
      </div>
    </aside>
  );
}

function stageStateLabel(status: string) {
  if (status === 'completed') return '已完成';
  return status === 'current' ? '进行中' : '未开始';
}
