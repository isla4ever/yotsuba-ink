import type { ExportFormat, ExportMetadata } from '../contracts';

export type { ExportFormat, ExportMetadata } from '../contracts';

export type ExportSelectionSnapshot = {
  chapter_ids: string[];
  format: ExportFormat;
  metadata: ExportMetadata;
};

export function freezeExportSelection(selection: ExportSelectionSnapshot): ExportSelectionSnapshot {
  return {
    chapter_ids: Array.from(new Set(selection.chapter_ids.map((id) => id.trim()).filter(Boolean))),
    format: selection.format,
    metadata: normalizeExportMetadata(selection.metadata),
  };
}

export function exportSelectionKey(selection: ExportSelectionSnapshot) {
  return JSON.stringify(freezeExportSelection(selection));
}

export function exportSelectionsEqual(left: ExportSelectionSnapshot, right: ExportSelectionSnapshot) {
  return exportSelectionKey(left) === exportSelectionKey(right);
}

export function toggleExportChapter(chapterIds: string[], selected: string[], chapterId: string) {
  const next = new Set(selected);
  if (next.has(chapterId)) next.delete(chapterId);
  else next.add(chapterId);
  return chapterIds.filter((id) => next.has(id));
}

export function exportPackageName(selection: ExportSelectionSnapshot, fallback: string) {
  const base = selection.metadata.bundle_name || selection.metadata.title || stripExportExtension(fallback) || 'novel-export';
  return `${base}.${selection.format}`;
}

export function normalizeExportMetadata(metadata: ExportMetadata): ExportMetadata {
  return {
    author: metadata.author.trim(),
    bundle_name: stripExportExtension(metadata.bundle_name.trim()),
    title: metadata.title.trim(),
    version_note: metadata.version_note.trim(),
  };
}

function stripExportExtension(value: string) {
  return value.replace(/\.(md|json|zip)$/i, '');
}
