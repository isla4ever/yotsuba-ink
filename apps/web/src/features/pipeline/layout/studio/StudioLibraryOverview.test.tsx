import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { StudioLibraryOverview } from './StudioLibraryOverview';

const project: ProjectRecord = {
  accent_hue: 160,
  created_at: '2026-08-01T00:00:00Z',
  id: 'project-1',
  latest_run_id: 'run-1',
  status: 'active',
  summary: '一部已完成的长篇。',
  title: '明日来电',
  updated_at: '2026-08-17T00:00:00Z',
  workflow_id: 'official-deepseek-balanced',
};

const summary: ProjectSummary = {
  completed_stage_ids: ['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export'],
  current_stage: {},
  latest_run: null,
  project,
  status: 'completed',
  title: project.title,
  updated_at: project.updated_at,
  words: 107_613,
};

describe('StudioLibraryOverview', () => {
  it('keeps the create command above the shelf and exposes persisted library metrics', () => {
    const html = renderToStaticMarkup(
      <StudioLibraryOverview loading={false} onCreate={() => undefined} projects={[project]} summaries={{ [project.id]: summary }} />,
    );
    expect(html).toContain('新建作品');
    expect(html).toContain('10.8 万字');
    expect(html).toContain('完整交付');
    expect(html).toContain('100%');
  });
});
