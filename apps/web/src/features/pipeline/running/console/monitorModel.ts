import type { RunEvent, StageType, WorkflowDefinition } from '../../contracts';
import { buildRunEventIndex, type StageRunStatus } from '../../state/runEventIndex';
import { stageDeliveryStatus } from '../../state/stageDeliveryStatus';
import {
  parseCoverArtifact,
  parseDetailArtifact,
  parseExportArtifact,
  parseSpineArtifact,
  parseStoryBriefArtifact,
  parseVolumesArtifact,
  type CoverArtifactVnext,
  type DetailArtifactVnext,
  type ExportArtifactVnext,
  type StoryBriefArtifact,
  type StorySpineArtifact,
  type VolumeArchitectureArtifact,
} from '../artifactsVnext';
import { parseCharacterBibleArtifact, type CharacterBibleArtifact } from '../characterBibleArtifact';
import { artifactText, eventStageId, latestApprovedArtifact, latestResult } from '../stageRunUtils';
import type { StickyArtifacts } from '../../state/runReducer';

export type MonitorChapterStatus = 'pending' | 'writing' | 'reviewing' | 'done';

export type MonitorChapterNode = {
  ref: string;
  title: string;
  purpose: string;
  pov: string;
  sceneCount: number;
  status: MonitorChapterStatus;
  words: number;
};

export type MonitorVolumeNode = {
  ref: string;
  ordinal: number;
  promise: string;
  chapters: MonitorChapterNode[];
};

export type MonitorStageEntry = {
  id: string;
  type: StageType;
  label: string;
  status: StageRunStatus;
  metric: string;
};

export type MonitorSnapshot = {
  activeStageId: string;
  activeStageType: StageType;
  stages: MonitorStageEntry[];
  tree: MonitorVolumeNode[];
  brief: StoryBriefArtifact | null;
  spine: StorySpineArtifact | null;
  cast: CharacterBibleArtifact | null;
  volumes: VolumeArchitectureArtifact | null;
  detail: DetailArtifactVnext | null;
  cover: CoverArtifactVnext | null;
  exportArtifact: ExportArtifactVnext | null;
  chapterBodies: Map<string, { title: string; content: string; completed: boolean }>;
  totals: { wordsWritten: number; chaptersDone: number; chaptersTotal: number; reviews: number; writebacks: number };
};

const emptySticky: StickyArtifacts = { chapters: {}, stages: {} };

/**
 * One pass over the newest-first run event log into everything the console renders.
 * `sticky` backfills artifacts whose events were evicted from the capped buffer
 * during long runs (a 40-chapter book emits ~1800 events against a 500 cap).
 */
export function buildMonitorSnapshot(
  events: RunEvent[],
  workflow: WorkflowDefinition,
  sticky: StickyArtifacts = emptySticky,
): MonitorSnapshot {
  const index = buildRunEventIndex(events);
  const brief = parseStoryBriefArtifact(stageArtifactSource(events, 'brief', sticky)).artifact;
  const spine = parseSpineArtifact(stageArtifactSource(events, 'spine', sticky)).artifact;
  const cast = parseCharacterBibleArtifact(stageArtifactSource(events, 'cast', sticky)).artifact;
  const volumes = parseVolumesArtifact(stageArtifactSource(events, 'volumes', sticky)).artifact;
  const detail = parseDetailArtifact(stageArtifactSource(events, 'detail', sticky)).artifact;
  const cover = parseCoverArtifact(stageArtifactSource(events, 'cover', sticky)).artifact;
  const exportArtifact = parseExportArtifact(stageArtifactSource(events, 'export', sticky)).artifact;
  const chapterBodies = chapterBodyMap(events, sticky);
  const tree = buildVolumeTree(volumes, detail, chapterBodies, events);
  const chaptersTotal = detail?.chapters.length ?? 0;
  const chaptersDone = tree.reduce(
    (sum, volume) => sum + volume.chapters.filter((chapter) => chapter.status === 'done').length,
    0,
  );
  const wordsWritten = tree.reduce(
    (sum, volume) => sum + volume.chapters.reduce((inner, chapter) => inner + chapter.words, 0),
    0,
  );
  const stages = workflow.nodes.map((stage) => {
    const status = stageDeliveryStatus(index, stage);
    // A stage whose lifecycle events fell out of the buffer reads as idle even
    // though its artifact was committed long ago; the sticky record corrects it.
    const committedOutsideWindow = sticky.stages[stage.id]?.type === 'artifact.committed';
    return {
      id: stage.id,
      type: stage.type,
      label: stage.label,
      status: status === 'idle' && committedOutsideWindow ? ('done' as StageRunStatus) : status,
      metric: stageMetric(stage.type, { brief, cast, chaptersDone, chaptersTotal, detail, events, spine, volumes }),
    };
  });
  return {
    activeStageId: activeStageIdFrom(events, stages),
    activeStageType: (stages.find((stage) => stage.id === activeStageIdFrom(events, stages))?.type ?? 'brief') as StageType,
    brief,
    cast,
    chapterBodies,
    cover,
    detail,
    exportArtifact,
    spine,
    stages,
    totals: {
      chaptersDone,
      chaptersTotal,
      reviews: events.filter((event) => event.type === 'review.completed').length,
      wordsWritten,
      writebacks: events.filter((event) => event.type === 'writeback.committed').length,
    },
    tree,
    volumes,
  };
}

/** Latest stage the run actually touched (events are newest-first); falls back to the first stage. */
function activeStageIdFrom(events: RunEvent[], stages: MonitorStageEntry[]): string {
  const known = new Set(stages.map((stage) => stage.id));
  for (const event of events) {
    if (event.type === 'checkpoint.saved') continue;
    const stageId = eventStageId(event);
    if (stageId && known.has(stageId)) return stageId;
  }
  return stages[0]?.id ?? 'brief';
}

function stageArtifactSource(events: RunEvent[], stageId: string, sticky: StickyArtifacts) {
  return (
    latestApprovedArtifact(events, stageId)
    || latestResult(events, stageId)
    || artifactText(sticky.stages[stageId]?.payload)
  );
}

function chapterBodyMap(events: RunEvent[], sticky: StickyArtifacts) {
  const map = new Map<string, { title: string; content: string; completed: boolean }>();
  // Sticky records first (survivors of buffer eviction), then the live window
  // oldest-first so fresher in-window revisions win.
  for (const event of [...Object.values(sticky.chapters), ...[...events].reverse()]) {
    if (!event.chapter_id || eventStageId(event) !== 'text') continue;
    if (event.type !== 'artifact.candidate_ready' && event.type !== 'artifact.committed') continue;
    const payload = event.payload ?? {};
    const content = typeof payload.content === 'string' ? payload.content : '';
    if (!content) continue;
    map.set(event.chapter_id, {
      completed: event.type === 'artifact.committed',
      content,
      title: typeof payload.title === 'string' ? payload.title : '',
    });
  }
  return map;
}

function buildVolumeTree(
  volumes: VolumeArchitectureArtifact | null,
  detail: DetailArtifactVnext | null,
  bodies: Map<string, { title: string; content: string; completed: boolean }>,
  events: RunEvent[],
): MonitorVolumeNode[] {
  if (!detail) return [];
  const grouped = new Map<string, MonitorChapterNode[]>();
  detail.chapters.forEach((chapter) => {
    const body = bodies.get(chapter.ref);
    const list = grouped.get(chapter.volume_ref) ?? [];
    list.push({
      pov: chapter.pov,
      purpose: chapter.purpose,
      ref: chapter.ref,
      sceneCount: chapter.scenes.length,
      status: chapterStatus(chapter.ref, body, events),
      title: meaningfulTitle(body?.title),
      words: body?.content.length ?? 0,
    });
    grouped.set(chapter.volume_ref, list);
  });
  const orderedRefs = volumes?.volumes.map((volume) => volume.id) ?? [...grouped.keys()];
  const promises = new Map((volumes?.volumes ?? []).map((volume) => [volume.id, volume.promise]));
  return orderedRefs
    .filter((ref) => grouped.has(ref))
    .map((ref, position) => ({
      chapters: grouped.get(ref) ?? [],
      ordinal: position + 1,
      promise: promises.get(ref) ?? '',
      ref,
    }));
}

/** Placeholder titles like 「第1章」 read worse than the blueprint purpose. */
function meaningfulTitle(title: string | undefined) {
  const value = (title ?? '').trim();
  return /^第\s*\d+\s*章$/.test(value) ? '' : value;
}

function chapterStatus(
  ref: string,
  body: { completed: boolean } | undefined,
  events: RunEvent[],
): MonitorChapterStatus {
  if (body?.completed) return 'done';
  if (body) return 'reviewing';
  const touched = events.some((event) => event.chapter_id === ref && eventStageId(event) === 'text');
  return touched ? 'writing' : 'pending';
}

type MetricSources = {
  brief: StoryBriefArtifact | null;
  cast: CharacterBibleArtifact | null;
  chaptersDone: number;
  chaptersTotal: number;
  detail: DetailArtifactVnext | null;
  events: RunEvent[];
  spine: StorySpineArtifact | null;
  volumes: VolumeArchitectureArtifact | null;
};

function stageMetric(type: StageType, sources: MetricSources): string {
  if (type === 'brief') return sources.brief ? sources.brief.title : '';
  if (type === 'spine') return sources.spine ? `${sources.spine.turns.length} 个转折` : '';
  if (type === 'cast') return sources.cast ? `${sources.cast.subjects.length} 位人物` : '';
  if (type === 'volumes') return sources.volumes ? `${sources.volumes.volumes.length} 卷` : '';
  if (type === 'detail') return sources.detail ? `${sources.detail.chapters.length} 章施工图` : '';
  if (type === 'text') return sources.chaptersTotal ? `${sources.chaptersDone}/${sources.chaptersTotal} 章` : '';
  if (type === 'cover') {
    const assets = sources.events.filter((event) => (
      eventStageId(event) === 'cover' && event.type === 'node.completed' && event.node_id.includes('generate')
    )).length;
    return assets ? `${assets} 次生成` : '';
  }
  const exported = sources.events.some((event) => eventStageId(event) === 'export' && event.type === 'artifact.committed');
  return exported ? '交付包已生成' : '';
}

export const monitorChapterStatusLabel: Record<MonitorChapterStatus, string> = {
  done: '已定稿',
  pending: '待创作',
  reviewing: '审校中',
  writing: '生成中',
};

export const monitorStageStatusLabel: Record<StageRunStatus, string> = {
  attention: '待完善',
  awaiting: '待决策',
  done: '已完成',
  failed: '失败',
  idle: '等待',
  running: '进行中',
};
