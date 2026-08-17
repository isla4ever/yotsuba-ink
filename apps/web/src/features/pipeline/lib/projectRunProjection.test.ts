import { describe, expect, it } from 'vitest';
import type { ProjectRecord } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { projectAfterRunEvent } from './projectRunProjection';

const project: ProjectRecord = {
  id: 'project-1',
  title: '待定书名',
  summary: '故事想法',
  accent_hue: 120,
  workflow_id: 'workflow-1',
  status: 'active',
  created_at: '2026-08-15T00:00:00Z',
  updated_at: '2026-08-15T00:00:00Z',
  latest_run_id: 'run-1',
};

describe('project run projection', () => {
  it('projects the formal title only from a committed Brief artifact', () => {
    const committed = runEvent('artifact.committed', {
      run_id: 'run-1',
      stage_id: 'brief',
      payload: { title: ' 潮汐证词 ' },
    });

    expect(projectAfterRunEvent(project, committed)).toEqual({
      ...project,
      title: '潮汐证词',
    });
  });

  it('does not project a title from candidates or unrelated commits', () => {
    expect(projectAfterRunEvent(project, runEvent('artifact.candidate_ready', {
      run_id: 'run-1',
      stage_id: 'brief',
      payload: { title: '候选书名' },
    }))).toBe(project);
    expect(projectAfterRunEvent(project, runEvent('artifact.committed', {
      run_id: 'run-1',
      stage_id: 'spine',
      payload: { title: '错误来源' },
    }))).toBe(project);
  });
});
