import type { ProjectRecord, RunEvent } from '../contracts';

export function projectAfterRunEvent(
  project: ProjectRecord | null,
  event: RunEvent,
): ProjectRecord | null {
  if (!project || event.type !== 'artifact.committed' || event.stage_id !== 'brief') {
    return project;
  }
  const title = typeof event.payload?.title === 'string' ? event.payload.title.trim() : '';
  if (!title || title === project.title) return project;
  return { ...project, title };
}
