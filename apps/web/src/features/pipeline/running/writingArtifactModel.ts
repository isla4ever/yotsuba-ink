import type { ChapterContextPacket, ChapterModelReview, ChapterQualityRecheck, ChapterWritebackProposal, RunEvent } from '../contracts';
import { modelReviewForChapter } from './modelReviewPresentation';
import { chaptersFrom, writingContentByChapter } from './stageRunUtils';

export type WritingRevision = {
  id: string;
  label: string;
  detail: string;
  status: string;
  type: string;
};

export type WritingVersion = {
  id: string;
  version: number;
  content: string;
  summary: string;
  words: number;
  summary_dirty: boolean;
  source: string;
  operation: string;
  created_at: string;
  artifact_signature: string;
};

export type WritingChapter = {
  id: string;
  title: string;
  generated_title: string;
  content: string;
  words: number;
  status: 'drafting' | 'committing' | 'completed';
  version: number;
  commit_signature: string;
  summary: string;
  summary_dirty: boolean;
  context_packet: ChapterContextPacket | null;
  wiki_writebacks: Array<Record<string, unknown>>;
  character_shift: unknown;
  foreshadow_updates: Array<Record<string, unknown>>;
  quality_report: Record<string, unknown>;
  quality_recheck: ChapterQualityRecheck | null;
  /** 10.4a additive：模型评审报告，fast 档与旧 Run 缺失（null）。 */
  model_review: ChapterModelReview | null;
  writeback_proposal: ChapterWritebackProposal | null;
  revision_history: WritingRevision[];
  version_history: WritingVersion[];
};

export type WritingArtifact = {
  schema_version: number;
  status: 'running' | 'completed';
  target_chapters: number;
  context_packet: Record<string, unknown>;
  context_packets: Array<Record<string, unknown>>;
  chapter_deltas: Array<Record<string, unknown>>;
  chapters: WritingChapter[];
  quality_reports: Array<Record<string, unknown>>;
  wiki_writebacks: Array<Record<string, unknown>>;
  chapter_summaries: Array<Record<string, unknown>>;
};

export type WritingReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export type ChapterReviewInsight = {
  chapter: string;
  qualityRecheck: ChapterQualityRecheck | null;
  proposal: ChapterWritebackProposal | null;
};

export function writingArtifact(value: string, events: RunEvent[]): WritingArtifact {
  const source = parseRecord(value);
  const sourceChapters = objectList(source?.chapters);
  const eventProgress = chaptersFrom(events);
  const eventContent = writingContentByChapter(events);
  const target = Math.max(numberValue(source?.target_chapters, 0), eventProgress.length, sourceChapters.length, 1);
  const chapterCount = Math.max(sourceChapters.length, eventProgress.length);
  const chapters = Array.from({ length: chapterCount }, (_, index) => {
    const raw = sourceChapters[index] ?? {};
    const title = text(raw.title, eventProgress[index]?.chapter || `第${index + 1}章`);
    const streamed = eventContent.get(title);
    const context = contextForChapter(events, title, raw.context_packet);
    return normalizeChapter(raw, index, title, streamed?.content ?? '', context, events);
  });
  return rebuildWritingArtifact({
    schema_version: numberValue(source?.schema_version, 1),
    status: source?.status === 'completed' ? 'completed' : chapters.length >= target && chapters.every((chapter) => chapter.status === 'completed') ? 'completed' : 'running',
    target_chapters: target,
    context_packet: objectRecord(source?.context_packet) ?? {},
    context_packets: objectList(source?.context_packets),
    chapter_deltas: objectList(source?.chapter_deltas),
    chapters,
    quality_reports: objectList(source?.quality_reports),
    wiki_writebacks: objectList(source?.wiki_writebacks),
    chapter_summaries: objectList(source?.chapter_summaries),
  });
}

export function updateWritingChapter(
  artifact: WritingArtifact,
  chapterId: string,
  patch: Partial<Pick<WritingChapter, 'content' | 'summary'>>,
): WritingArtifact {
  const chapters = artifact.chapters.map((chapter) => {
    if (chapter.id !== chapterId) return chapter;
    const contentChanged = patch.content !== undefined && patch.content !== chapter.content;
    const summaryChanged = patch.summary !== undefined && patch.summary !== chapter.summary;
    const hasDraftRevision = chapter.revision_history.some((revision) => revision.type === 'manual_edit' && revision.status === 'draft');
    const version = contentChanged && !hasDraftRevision ? chapter.version + 1 : chapter.version;
    const manualRevision = contentChanged ? upsertManualRevision(chapter.revision_history, version) : chapter.revision_history;
    return {
      ...chapter,
      ...patch,
      words: patch.content !== undefined ? patch.content.trim().length : chapter.words,
      commit_signature: contentChanged || summaryChanged ? '' : chapter.commit_signature,
      summary_dirty: contentChanged || summaryChanged ? true : chapter.summary_dirty,
      quality_recheck: contentChanged || summaryChanged ? null : chapter.quality_recheck,
      writeback_proposal: contentChanged || summaryChanged ? null : chapter.writeback_proposal,
      version,
      revision_history: manualRevision,
    };
  });
  return rebuildWritingArtifact({ ...artifact, chapters });
}

export function writingReadiness(artifact: WritingArtifact): WritingReadiness {
  const missingLabels: string[] = [];
  for (let index = 0; index < artifact.target_chapters; index += 1) {
    const chapter = artifact.chapters[index];
    const label = chapter?.title || `第${index + 1}章`;
    if (!chapter) {
      missingLabels.push(`${label}正文`);
      continue;
    }
    if (!chapter.id || !chapter.title || !chapter.content.trim() || chapter.words <= 0 || chapter.status !== 'completed') {
      missingLabels.push(`${label}正文`);
    }
    if (!chapter.context_packet?.chapter || !chapter.context_packet.chapter_outline?.trim()) {
      missingLabels.push(`${label}上下文`);
    }
    if (!chapter.summary.trim()) missingLabels.push(`${label}摘要`);
    if (chapter.summary_dirty) missingLabels.push(`${label}摘要同步`);
    if (chapter.quality_recheck?.status === 'blocked') missingLabels.push(`${label}质量复检`);
    if (chapter.writeback_proposal?.status === 'pending') {
      missingLabels.push(`${label}写回提案决策`);
    }
  }
  return {
    completed: artifact.chapters.filter((chapter) => chapter.status === 'completed').length,
    missingLabels: [...new Set(missingLabels)],
    ready: missingLabels.length === 0 && artifact.chapters.length >= artifact.target_chapters,
    total: artifact.target_chapters,
  };
}

export function chapterReviewInsight(artifact: WritingArtifact, chapterId = ''): ChapterReviewInsight | undefined {
  const selected = chapterId ? artifact.chapters.find((item) => item.id === chapterId) : undefined;
  const chapter = selected
    ? selected
    : artifact.chapters
      .filter((item) => item.quality_recheck || item.writeback_proposal)
      .reduce<WritingChapter | undefined>((latest, item) => (
        !latest || reviewTime(item) >= reviewTime(latest) ? item : latest
      ), undefined);
  if (!chapter) return undefined;
  return {
    chapter: chapter.title,
    qualityRecheck: chapter.quality_recheck,
    proposal: chapter.writeback_proposal,
  };
}

function reviewTime(chapter: WritingChapter) {
  const parsed = Date.parse(chapter.writeback_proposal?.created_at ?? '');
  return Number.isFinite(parsed) ? parsed : chapter.version;
}

export function contextForChapter(
  events: RunEvent[],
  chapter: string,
  saved?: unknown,
): ChapterContextPacket | null {
  const stored = objectRecord(saved);
  if (stored?.chapter === chapter) return stored as ChapterContextPacket;
  return events.find(
    (event) => event.type === 'chapter_context_built'
      && event.chapter === chapter
      && event.context_packet?.chapter === chapter,
  )?.context_packet ?? null;
}

export function revisionHistoryForChapter(events: RunEvent[], chapter: string): WritingRevision[] {
  return [...events]
    .reverse()
    .filter((event) => event.chapter === chapter && [
      'revision_directive_created',
      'revision_applied',
      'quality_recheck_completed',
      'manual_intervention_required',
    ].includes(event.type))
    .map((event, index) => ({
      id: String(event.directive?.id || `${event.type}-${index}`),
      label: revisionLabel(event.type),
      detail: String(event.directive?.instruction || event.directive?.issue || event.reason || event.message || '已记录章节质量变化'),
      status: String(event.directive?.status || (event.type === 'manual_intervention_required' ? 'blocking' : 'completed')),
      type: event.type,
    }));
}

function normalizeChapter(
  raw: Record<string, unknown>,
  index: number,
  title: string,
  streamedContent: string,
  context: ChapterContextPacket | null,
  events: RunEvent[],
): WritingChapter {
  const content = text(raw.content, streamedContent);
  const eventRevisions = revisionHistoryForChapter(events, title);
  const savedRevisions = objectList(raw.revision_history).map(normalizeRevision);
  return {
    id: text(raw.id, `chapter-${index + 1}`),
    title,
    generated_title: text(raw.generated_title, title),
    content,
    words: numberValue(raw.words, content.trim().length),
    status: chapterStatus(raw.status, events, title),
    version: numberValue(raw.version, raw.status === 'completed' ? 1 : 0),
    commit_signature: text(raw.commit_signature, ''),
    summary: text(raw.summary, summaryFromTop(events, title)),
    summary_dirty: Boolean(raw.summary_dirty),
    context_packet: context,
    wiki_writebacks: objectList(raw.wiki_writebacks),
    character_shift: raw.character_shift ?? '',
    foreshadow_updates: objectList(raw.foreshadow_updates),
    quality_report: objectRecord(raw.quality_report) ?? {},
    quality_recheck: objectRecord(raw.quality_recheck) as ChapterQualityRecheck | null,
    model_review: modelReviewForChapter(raw.model_review, events, title),
    writeback_proposal: objectRecord(raw.writeback_proposal) as ChapterWritebackProposal | null,
    revision_history: mergeRevisions(savedRevisions, eventRevisions),
    version_history: objectList(raw.version_history).map(normalizeVersion),
  };
}

function rebuildWritingArtifact(artifact: WritingArtifact): WritingArtifact {
  const contextPackets = artifact.chapters.flatMap((chapter) => chapter.context_packet ? [chapter.context_packet as unknown as Record<string, unknown>] : []);
  return {
    ...artifact,
    status: artifact.chapters.length >= artifact.target_chapters && artifact.chapters.every((chapter) => chapter.status === 'completed') ? 'completed' : 'running',
    context_packet: contextPackets[contextPackets.length - 1] ?? {},
    context_packets: contextPackets,
    quality_reports: artifact.chapters.flatMap((chapter) => Object.keys(chapter.quality_report).length ? [chapter.quality_report] : []),
    wiki_writebacks: artifact.chapters.flatMap((chapter) => chapter.wiki_writebacks),
    chapter_summaries: artifact.chapters.filter((chapter) => chapter.summary.trim()).map((chapter) => ({ chapter: chapter.title, summary: chapter.summary })),
  };
}

function chapterStatus(value: unknown, events: RunEvent[], chapter: string): WritingChapter['status'] {
  if (value === 'drafting' || value === 'committing' || value === 'completed') return value;
  return events.some((event) => event.type === 'chapter_completed' && event.chapter === chapter) ? 'completed' : 'drafting';
}

function summaryFromTop(events: RunEvent[], chapter: string) {
  const completed = events.find((event) => event.type === 'chapter_completed' && event.chapter === chapter);
  const artifact = objectRecord(completed?.artifact);
  return text(artifact?.summary, '');
}

function normalizeRevision(value: Record<string, unknown>, index: number): WritingRevision {
  return {
    id: text(value.id, `revision-${index + 1}`),
    label: text(value.label, revisionLabel(text(value.type, 'revision'))),
    detail: text(value.detail ?? value.instruction ?? value.issue, '已记录修订'),
    status: text(value.status, 'completed'),
    type: text(value.type, 'revision'),
  };
}

function normalizeVersion(value: Record<string, unknown>, index: number): WritingVersion {
  return {
    id: text(value.id, `version-${index + 1}`),
    version: numberValue(value.version, index + 1),
    content: text(value.content, ''),
    summary: text(value.summary, ''),
    words: numberValue(value.words, 0),
    summary_dirty: Boolean(value.summary_dirty),
    source: text(value.source, 'model_generation'),
    operation: text(value.operation, ''),
    created_at: text(value.created_at, ''),
    artifact_signature: text(value.artifact_signature, ''),
  };
}

function upsertManualRevision(revisions: WritingRevision[], version: number) {
  const next = revisions.filter((revision) => revision.type !== 'manual_edit' || revision.status !== 'draft');
  return [...next, { id: `manual-draft-v${version}`, label: `人工修订 v${version}`, detail: '正文已修改，需同步章节摘要后定稿。', status: 'draft', type: 'manual_edit' }];
}

function mergeRevisions(saved: WritingRevision[], eventRevisions: WritingRevision[]) {
  const merged = [...saved];
  eventRevisions.forEach((revision) => {
    if (!merged.some((item) => item.id === revision.id)) merged.push(revision);
  });
  return merged;
}

function revisionLabel(type: string) {
  return {
    revision_directive_created: '质量修订指令',
    revision_applied: '模型修订已应用',
    quality_recheck_completed: '修订复检完成',
    manual_intervention_required: '需要人工处理',
    manual_edit: '人工修订',
  }[type] ?? '章节修订';
}

function parseRecord(value: string): Record<string, unknown> | null {
  try {
    return objectRecord(JSON.parse(value));
  } catch {
    return null;
  }
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function objectList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(objectRecord).filter((item): item is Record<string, unknown> => Boolean(item)) : [];
}

function text(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function numberValue(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
