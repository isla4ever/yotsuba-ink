import type { ChapterContextPacket } from '../contracts';
import type { DetailOutlineArtifact } from './stageArtifacts';

export type TrustedCharacterState = { name: string; status: string };
export type DetailChapterContext = DetailOutlineArtifact['chapters'][number];

export function chapterKindLabel(context: ChapterContextPacket | null, hasDetailFallback = false) {
  const labels: Record<string, string> = {
    first: '首章',
    normal: '常规章',
    volume_start: '卷首章',
    volume_end: '卷末章',
    finale: '终章',
  };
  return labels[context?.chapter_kind ?? ''] ?? (hasDetailFallback ? '细纲回溯' : '待写入');
}

export function chapterOutlinePresentation(
  context: ChapterContextPacket | null,
  detailChapter?: DetailChapterContext,
) {
  const stored = context?.chapter_outline?.trim();
  if (stored) return stored;
  if (!detailChapter) return '当前章节细纲尚未写入。';
  return [
    `${detailChapter.pov || '本章主角'}在${detailChapter.scene || '待定场景'}推进：${detailChapter.goal || '章节目标待补充'}。`,
    detailChapter.entry_state ? `进入状态：${detailChapter.entry_state}。` : '',
    detailChapter.conflict ? `核心冲突：${detailChapter.conflict}。` : '',
    detailChapter.stakes ? `风险：${detailChapter.stakes}。` : '',
    detailChapter.hook ? `章末钩子：${detailChapter.hook}。` : '',
    detailChapter.continuity_notes ? `正文交接：${detailChapter.continuity_notes}` : '',
  ].filter(Boolean).join(' ');
}

export function trustedContextRules(context: ChapterContextPacket | null) {
  return (context?.world_rules ?? [])
    .map((rule) => String(rule).trim())
    .filter((rule) => rule.length > 0 && rule.length <= 220)
    .slice(0, 3);
}

export function trustedForeshadowLines(context: ChapterContextPacket | null) {
  return (context?.open_foreshadows ?? [])
    .map((item, index) => {
      const value = item && typeof item === 'object' && !Array.isArray(item) ? item as Record<string, unknown> : {};
      return [value.name || value.summary || `伏笔 ${index + 1}`, value.status, value.note]
        .filter(Boolean)
        .map(String)
        .join(' · ')
        .trim();
    })
    .filter((line) => line.length > 0 && line.length <= 220)
    .slice(0, 4);
}

export function previousChapterContext(context: ChapterContextPacket | null) {
  if (context?.chapter_kind === 'first' || context?.chapter_index === 1) {
    return context?.transition_directive?.trim() || '首章，无前章承接。';
  }
  const directive = context?.transition_directive?.trim();
  const previous = context?.previous_chapter_summary?.trim();
  return [directive, previous ? `前章摘要：${previous}` : '等待前章摘要。'].filter(Boolean).join('\n');
}

export function trustedCharacterStates(
  characterState: Record<string, unknown> | undefined,
  trustedNames: string[],
): TrustedCharacterState[] {
  const trusted = new Set(trustedNames.map((name) => name.trim()).filter(Boolean));
  if (!trusted.size) return [];
  return Object.entries(characterState ?? {}).flatMap(([key, value]) => {
    const record = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
    const name = String(record?.name || key).trim();
    if (!trusted.has(name)) return [];
    const status = String(record?.status || record?.motivation || record?.role || value || '状态已载入').trim();
    return [{ name, status }];
  }).slice(0, 4);
}
