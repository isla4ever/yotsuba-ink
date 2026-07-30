import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ProjectCard, ProjectCardWall } from './ProjectCardWall';
import type { ProjectRecord, ProjectSummary } from '../../contracts';

const project: ProjectRecord = {
  id: 'proj-1',
  title: '雾城异闻',
  summary: '港口旧案与记忆实验的双线悬疑。',
  accent_hue: 262,
  workflow_id: 'wf-proj-1',
  status: 'active',
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-20T00:00:00Z',
  latest_run_id: 'run-1',
};

const summary = {
  project,
  latest_run: null,
  title: '雾城异闻',
  status: 'awaiting_confirmation',
  current_stage: { id: 'detail', label: '章节细纲' },
  completed_stage_ids: ['info', 'summary', 'outline'],
  words: 42_000,
  updated_at: '2026-07-25T00:00:00Z',
} as ProjectSummary;

describe('ProjectCard', () => {
  it('renders the seven-dot progress matrix from real stage facts plus words and status', () => {
    const html = renderToStaticMarkup(
      <ProjectCard onOpen={() => undefined} project={project} summary={summary} />,
    );
    expect(html.match(/studio-progress-dot completed/g)).toHaveLength(3);
    expect(html.match(/studio-progress-dot current/g)).toHaveLength(1);
    expect(html.match(/studio-progress-dot pending/g)).toHaveLength(3);
    expect(html).toContain('4.2 万字');
    expect(html).toContain('待确认');
    expect(html).toContain('--project-accent-hue:262');
  });
});

describe('ProjectCardWall', () => {
  it('shows the quiet empty state with a single create entry when there are no projects', () => {
    const html = renderToStaticMarkup(
      <ProjectCardWall error="" loading={false} onCreate={() => undefined} onOpen={() => undefined} projects={[]} summaries={{}} />,
    );
    expect(html).toContain('studio-empty-state');
    expect(html).toContain('新建作品');
    expect(html).not.toContain('studio-card-wall');
  });

  it('renders one card per project plus the dashed new-project card', () => {
    const html = renderToStaticMarkup(
      <ProjectCardWall
        error=""
        loading={false}
        onCreate={() => undefined}
        onOpen={() => undefined}
        projects={[project, { ...project, id: 'proj-2', title: '第二部' }]}
        summaries={{ [project.id]: summary }}
      />,
    );
    expect(html.match(/studio-project-card/g)?.length).toBe(2);
    expect(html).toContain('studio-new-card');
  });
});
