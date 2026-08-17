import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ProjectBookshelf } from './ProjectBookshelf';
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
  status: 'awaiting_decision',
  current_stage: { id: 'detail', label: '章节施工图' },
  completed_stage_ids: ['brief', 'spine', 'volumes'],
  words: 42_000,
  updated_at: '2026-07-25T00:00:00Z',
} as ProjectSummary;

describe('ProjectBookshelf', () => {
  it('shows the quiet empty state with a single create entry when there are no projects', () => {
    const html = renderToStaticMarkup(
      <ProjectBookshelf error="" loading={false} onOpen={() => undefined} projects={[]} summaries={{}} />,
    );
    expect(html).toContain('studio-empty-state');
    expect(html).not.toContain('tech-button');
    expect(html).not.toContain('studio-shelf');
  });

  it('renders exactly one spine per project and keeps creation outside the shelf', () => {
    const html = renderToStaticMarkup(
      <ProjectBookshelf
        error=""
        loading={false}
        onOpen={() => undefined}
        projects={[project, { ...project, id: 'proj-2', title: '第二部' }]}
        summaries={{ [project.id]: summary }}
      />,
    );
    expect(html.match(/studio-book-spine/g)?.length).toBe(2);
    expect(html).not.toContain('new-book');
    expect(html).toContain('studio-book-desk');
    expect(html).toContain('studio-shelf-control prev');
    expect(html).toContain('studio-shelf-control next');
    expect(html).toContain('project-shelf-rail');
    expect(html).toContain('4.2 万字');
    expect(html).toContain('--project-accent-hue:262');
  });

  it('projects the eight-dot progress matrix and run status on the desk panel', () => {
    const html = renderToStaticMarkup(
      <ProjectBookshelf
        error=""
        loading={false}
        onOpen={() => undefined}
        projects={[project]}
        summaries={{ [project.id]: summary }}
      />,
    );
    expect(html.match(/studio-progress-dot completed/g)).toHaveLength(3);
    expect(html.match(/studio-progress-dot current/g)).toHaveLength(1);
    expect(html.match(/studio-progress-dot pending/g)).toHaveLength(4);
    expect(html).toContain('待决策');
    expect(html).toContain('八阶段进度');
  });
});
