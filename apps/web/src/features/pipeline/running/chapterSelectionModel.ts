import type { ChapterQualityRepairTarget, ChapterSelection } from '../contracts';
import type { WritingChapter } from './writingArtifactModel';

export function chapterSelection(
  content: string,
  start: number,
  end: number,
): ChapterSelection | null {
  if (start < 0 || end <= start || end > content.length) return null;
  const selected = content.slice(start, end);
  if (!selected.trim() || selected.length > 6000) return null;
  return { start, end, text: selected };
}

export async function chapterRevisionSignature(
  chapter: Pick<WritingChapter, 'id' | 'version' | 'content' | 'summary' | 'summary_dirty'>,
) {
  const payload = [
    chapter.id,
    String(chapter.version),
    chapter.content,
    chapter.summary,
    chapter.summary_dirty ? '1' : '0',
  ].join('\0');
  const digest = await globalThis.crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(payload),
  );
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
}

export async function chapterRepairSelection(
  chapter: Pick<WritingChapter, 'id' | 'version' | 'content' | 'summary' | 'summary_dirty'>,
  target: ChapterQualityRepairTarget,
): Promise<ChapterSelection | null> {
  if (!target.locatable || target.chapter_id !== chapter.id || target.chapter_version !== chapter.version) return null;
  if (target.artifact_signature !== await chapterRevisionSignature(chapter)) return null;
  const selection = chapterSelection(chapter.content, target.start, target.end);
  return selection?.text === target.selected_text ? selection : null;
}

export function chapterRevisionRequestId(prefix: string) {
  const id = typeof globalThis.crypto.randomUUID === 'function'
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${id}`;
}
