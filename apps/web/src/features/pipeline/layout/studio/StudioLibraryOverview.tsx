import { BookOpenText, CircleCheckBig, FileText, Gauge, Plus } from 'lucide-react';
import type { CSSProperties } from 'react';
import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { RevealText } from '../RevealText';
import { formatWordCount, studioLibraryStats } from './studioModel';

type Props = {
  loading: boolean;
  onCreate: () => void;
  projects: ProjectRecord[];
  summaries: Record<string, ProjectSummary>;
};

export function StudioLibraryOverview({ loading, onCreate, projects, summaries }: Props) {
  const stats = studioLibraryStats(projects, summaries);
  return (
    <header className="studio-library-overview">
      <div className="studio-library-heading">
        <div>
          <RevealText as="h1" className="studio-section-title" id="studio-projects-heading" text="作品库" />
          <p>{loading ? '正在同步作品状态...' : '集中查看作品进度与最近定稿状态'}</p>
        </div>
        <button className="tech-button studio-create-project" onClick={onCreate} type="button">
          <Plus aria-hidden="true" size={16} />
          新建作品
        </button>
      </div>
      <dl
        className="studio-library-metrics"
        style={{ '--studio-stage-coverage': `${stats.stageCoverage}%` } as CSSProperties}
      >
        <div><BookOpenText aria-hidden="true" size={16} /><dt>作品总数</dt><dd>{stats.projectCount}</dd></div>
        <div><FileText aria-hidden="true" size={16} /><dt>累计正文</dt><dd>{formatWordCount(stats.totalWords)}</dd></div>
        <div><CircleCheckBig aria-hidden="true" size={16} /><dt>完整交付</dt><dd>{stats.completedProjects}</dd></div>
        <div className="studio-stage-coverage"><Gauge aria-hidden="true" size={16} /><dt>阶段完成率</dt><dd>{stats.stageCoverage}%</dd><i aria-hidden="true" /></div>
      </dl>
    </header>
  );
}
