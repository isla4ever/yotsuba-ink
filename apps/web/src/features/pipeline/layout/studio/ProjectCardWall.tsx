import { Plus } from 'lucide-react';
import type { CSSProperties } from 'react';
import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { ButtonLoadingIndicator } from '../ButtonLoadingIndicator';
import { ManuscriptLoadingIndicator } from '../ManuscriptLoadingIndicator';
import {
  formatWordCount,
  relativeTimeLabel,
  runStatusLabel,
  stageProgressDots,
} from './studioModel';

type CardProps = {
  opening?: boolean;
  project: ProjectRecord;
  summary: ProjectSummary | null;
  onOpen: (project: ProjectRecord, summary: ProjectSummary | null) => void;
};

export function ProjectCard({ opening = false, project, summary, onOpen }: CardProps) {
  const dots = stageProgressDots(summary);
  const words = summary?.words ?? 0;
  const updatedAt = summary?.updated_at || project.updated_at;
  const runStatus = runStatusLabel(summary?.status ?? '');
  return (
    <button
      aria-busy={opening || undefined}
      className="studio-project-card"
      disabled={opening}
      onClick={() => onOpen(project, summary)}
      style={{ '--project-accent-hue': project.accent_hue } as CSSProperties}
      title={`打开「${project.title}」`}
      type="button"
    >
      <span aria-hidden="true" className="studio-card-accent" />
      <div className="studio-card-head">
        <h3>{project.title}</h3>
        <span className={`studio-card-status ${project.status}${opening ? ' opening' : ''}`}>
          {opening ? <><ButtonLoadingIndicator />正在打开</> : project.status === 'archived' ? '已归档' : runStatus || '创作中'}
        </span>
      </div>
      <p className="studio-card-summary">{project.summary || summary?.latest_run?.summary || '尚未填写概要。'}</p>
      <div aria-label="七阶段进度" className="studio-card-progress" role="img">
        {dots.map((dot) => (
          <span
            aria-hidden="true"
            className={`studio-progress-dot ${dot.status}`}
            key={dot.id}
            title={`${dot.label} · ${dot.status === 'completed' ? '已完成' : dot.status === 'current' ? '进行中' : '未开始'}`}
          />
        ))}
        <span className="sidebar-visually-hidden">
          {dots.filter((dot) => dot.status === 'completed').length} / {dots.length} 阶段完成
        </span>
      </div>
      <div className="studio-card-meta">
        <span className="studio-card-words">{formatWordCount(words)}</span>
        <span>{relativeTimeLabel(updatedAt)}</span>
      </div>
    </button>
  );
}

type WallProps = {
  projects: ProjectRecord[];
  summaries: Record<string, ProjectSummary>;
  loading: boolean;
  error: string;
  onOpen: (project: ProjectRecord, summary: ProjectSummary | null) => void;
  onCreate: () => void;
  openingProjectId?: string;
};

export function ProjectCardWall({ projects, summaries, loading, error, onOpen, onCreate, openingProjectId = '' }: WallProps) {
  if (loading && !projects.length && !error) {
    return <div className="studio-loading-state" role="status"><ManuscriptLoadingIndicator /><strong>正在同步作品库</strong><span>读取作品、运行摘要与模板状态</span></div>;
  }
  if (!loading && !error && projects.length === 0) {
    return (
      <div className="studio-empty-state">
        <h2>尚无作品</h2>
        <p>新建第一部作品，进入创作规划。</p>
        <button className="tech-button" onClick={onCreate} type="button">
          <Plus aria-hidden="true" size={16} />
          新建作品
        </button>
      </div>
    );
  }
  return (
    <>
      {error ? <p className="studio-inline-error" role="alert">{error}</p> : null}
      <div className="studio-card-wall">
        {projects.map((project) => (
          <ProjectCard
            key={project.id}
            opening={openingProjectId === project.id}
            onOpen={onOpen}
            project={project}
            summary={summaries[project.id] ?? null}
          />
        ))}
        <button className="studio-new-card" onClick={onCreate} type="button">
          <Plus aria-hidden="true" size={18} />
          <span>新建作品</span>
        </button>
      </div>
    </>
  );
}
