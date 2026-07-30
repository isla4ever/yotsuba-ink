import type { RunEvent, TensionTrackEntry } from '../contracts';
import type { WritingChapter } from './writingArtifactModel';

export const TENSION_MAX = 10;

export type TensionPoint = {
  basis: string;
  chapterId: string;
  index: number;
  isCurrent: boolean;
  score: number | null;
  title: string;
  xFraction: number;
};

export type TensionSeries = {
  empty: boolean;
  points: TensionPoint[];
  scoredCount: number;
  /** 连续有分数的点段；缺分章节把段切断（不插值——插值是伪造）。 */
  segments: TensionPoint[][];
  source: 'events' | 'story_bible' | 'none';
};

type TensionEntry = { basis: string; score: number };

/**
 * 张力数据来源（Phase 10.3c）：优先 `chapter_tension_scored` 运行事件按章 upsert
 * （events 列表是最新在前，同章取第一条即最新分数），回退最近一条
 * `story_bible_updated` 的 `story_bible.tension_track`；两者皆无 → source 'none'。
 */
export function tensionEntriesFrom(events: RunEvent[]): { entries: Map<string, TensionEntry>; source: TensionSeries['source'] } {
  const entries = new Map<string, TensionEntry>();
  for (const event of events) {
    if (event.type !== 'chapter_tension_scored') continue;
    const chapter = (event.chapter ?? '').trim();
    const score = Number(event.score);
    if (!chapter || !Number.isFinite(score) || entries.has(chapter)) continue;
    entries.set(chapter, { basis: String(event.basis ?? '').trim(), score: clampScore(score) });
  }
  if (entries.size) return { entries, source: 'events' };
  const track = latestBibleTrack(events);
  track.forEach((item) => {
    const chapter = item.chapter.trim();
    if (chapter && Number.isFinite(item.score)) entries.set(chapter, { basis: item.basis.trim(), score: clampScore(item.score) });
  });
  return { entries, source: entries.size ? 'story_bible' : 'none' };
}

export function buildTensionSeries(chapters: WritingChapter[], events: RunEvent[], activeChapterId: string): TensionSeries {
  const { entries, source } = tensionEntriesFrom(events);
  const points = chapters.map((chapter, index) => {
    const entry = entries.get(chapter.title.trim()) ?? entries.get(chapter.generated_title.trim());
    return {
      basis: entry?.basis ?? '',
      chapterId: chapter.id,
      index,
      isCurrent: chapter.id === activeChapterId,
      score: entry ? entry.score : null,
      title: chapter.generated_title || chapter.title,
      xFraction: (index + 0.5) / Math.max(1, chapters.length),
    };
  });
  const scored = points.filter((point) => point.score != null);
  const segments: TensionPoint[][] = [];
  points.forEach((point) => {
    if (point.score == null) return;
    const last = segments[segments.length - 1];
    if (last && last[last.length - 1].index === point.index - 1) last.push(point);
    else segments.push([point]);
  });
  return {
    empty: !scored.length,
    points,
    scoredCount: scored.length,
    segments,
    source: scored.length ? source : 'none',
  };
}

export function tensionPointDescription(point: TensionPoint): string {
  const position = `第 ${point.index + 1} 章 ${point.title}`;
  if (point.score == null) return `${position}：暂无张力评分`;
  const basis = point.basis ? `，依据：${point.basis}` : '';
  return `${position}：张力 ${point.score.toFixed(1)}/${TENSION_MAX}${basis}`;
}

function latestBibleTrack(events: RunEvent[]): TensionTrackEntry[] {
  for (const event of events) {
    if (event.type !== 'story_bible_updated') continue;
    const track = (event.story_bible as { tension_track?: unknown } | undefined)?.tension_track;
    if (!Array.isArray(track)) continue;
    const parsed = track
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
      .map((item) => ({
        basis: String(item.basis ?? ''),
        chapter: String(item.chapter ?? ''),
        score: Number(item.score),
        source: item.source == null ? undefined : String(item.source),
      }))
      .filter((item) => item.chapter.trim() && Number.isFinite(item.score));
    if (parsed.length) return parsed;
  }
  return [];
}

function clampScore(score: number) {
  return Math.min(TENSION_MAX, Math.max(0, score));
}
