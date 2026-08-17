import type { RunEvent } from '../contracts';
import { parseDetailArtifact } from './artifactsVnext';
import { latestApprovedArtifact } from './stageRunUtils';

export function projectExportChapterTitles(events: RunEvent[], versionIds: string[]) {
  const titleByVersion = new Map<string, string>();

  events.forEach((event) => {
    if (event.stage_id !== 'text' || event.type !== 'artifact.committed' || !event.payload) return;
    const title = textValue(event.payload.title);
    if (!title) return;
    const versionId = textValue(event.payload.version_id) || event.payload_ref;
    if (versionId && !titleByVersion.has(versionId)) titleByVersion.set(versionId, title);
  });

  const detail = parseDetailArtifact(latestApprovedArtifact(events, 'detail')).artifact;
  return versionIds.map((versionId, index) => (
    titleByVersion.get(versionId)
    || detail?.chapters[index]?.title.trim()
    || `第 ${index + 1} 章`
  ));
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}
