import { list, objectList, objectRecord, parseArtifactRecord, text } from './artifactParsing';
import type { ExportCoverAsset } from '../contracts';
import { exportDeliveryReady, normalizeExportValidation } from './exportValidation';

export type ExportArtifact = {
  bundle_name: string;
  chapters?: Array<{ id: string; title: string; content?: string; words?: number; status?: string }>;
  files: Array<{ name: string; format: string; status: string }>;
  formats: Array<'md' | 'json' | 'zip'>;
  metadata: { title: string; author: string; version_note: string; bundle_name: string };
  default_format: 'md' | 'json' | 'zip';
  cover_asset: ExportCoverAsset | null;
  validation: Record<string, string>;
  package_ready: boolean;
};

export function exportArtifact(value: string): ExportArtifact {
  const record = parseArtifactRecord(value);
  const files = objectList<ExportArtifact['files'][number]>(record?.manifest, []);
  const packageStatus = objectRecord(record?.package_status);
  const metadata = objectRecord(record?.metadata);
  const cover = objectRecord(record?.cover_asset);
  const chapters = objectList<NonNullable<ExportArtifact['chapters']>[number]>(record?.chapters, []);
  const coverAsset: ExportCoverAsset | null = cover?.asset_id ? {
    candidate_id: text(cover.candidate_id, ''),
    asset_id: text(cover.asset_id, ''),
    sha256: text(cover.sha256, ''),
    mime_type: text(cover.mime_type, ''),
    width: Number(cover.width || 0),
    height: Number(cover.height || 0),
    size_bytes: Number(cover.size_bytes || 0),
    image_url: text(cover.image_url, ''),
  } : null;
  const validation = normalizeExportValidation(
    objectRecord(record?.validation) as Record<string, string> ?? {},
    { hasChapters: chapters.length > 0, hasCoverAsset: Boolean(coverAsset) },
  );
  const formats = list(record?.formats, []).filter((item): item is ExportArtifact['formats'][number] => ['md', 'json', 'zip'].includes(item));
  return {
    bundle_name: text(packageStatus?.name, 'novel-export'),
    chapters,
    files,
    formats: formats.length ? formats : ['md', 'json', 'zip'],
    metadata: {
      title: text(metadata?.title, ''),
      author: text(metadata?.author, ''),
      version_note: text(metadata?.version_note, ''),
      bundle_name: text(metadata?.bundle_name, text(packageStatus?.name, 'novel-export')),
    },
    default_format: exportFormat(packageStatus?.kind),
    cover_asset: coverAsset,
    validation,
    package_ready: Boolean(packageStatus?.ready) && exportDeliveryReady(validation),
  };
}

function exportFormat(value: unknown): ExportArtifact['default_format'] {
  return ['md', 'json', 'zip'].includes(String(value)) ? value as ExportArtifact['default_format'] : 'md';
}
