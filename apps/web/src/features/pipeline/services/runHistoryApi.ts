import type {
  ExportReceipt,
  RunHistoryItem,
  RunHistoryResponse,
  RunSnapshotItem,
  RunSnapshotsResponse,
} from '../contracts';
import { verifyExportBlob } from './exportIntegrity';
import { RunApiError } from './runApi';

export async function listRunHistory(params: {
  limit?: number;
  cursor?: string;
  projectId?: string;
  status?: string;
} = {}, signal?: AbortSignal): Promise<RunHistoryResponse> {
  const query = new URLSearchParams();
  if (params.limit) query.set('limit', String(params.limit));
  if (params.cursor) query.set('cursor', params.cursor);
  if (params.projectId) query.set('project_id', params.projectId);
  if (params.status) query.set('status', params.status);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`/api/runs/history${suffix}`, { signal });
  if (!response.ok) throw await historyError(response, `/api/runs/history${suffix}`);
  const payload = await response.json() as Partial<RunHistoryResponse>;
  return {
    items: Array.isArray(payload.items) ? payload.items.map(normalizeHistoryItem) : [],
    next_cursor: typeof payload.next_cursor === 'string' ? payload.next_cursor : '',
  };
}

export async function listRunSnapshots(runId: string, signal?: AbortSignal): Promise<RunSnapshotsResponse> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/snapshots`, { signal });
  if (!response.ok) throw await historyError(response, `/api/runs/${runId}/snapshots`);
  const payload = await response.json() as Partial<RunSnapshotsResponse>;
  return {
    run_id: String(payload.run_id || runId),
    state_revision: Number(payload.state_revision || 0),
    items: Array.isArray(payload.items) ? payload.items as RunSnapshotItem[] : [],
    latest_restorable_snapshot_id: String(payload.latest_restorable_snapshot_id || ''),
  };
}

export async function restoreRunSnapshot(
  runId: string,
  payload: { snapshot_id: string; request_id: string; expected_revision?: number },
): Promise<{ run_id: string; snapshot_id: string; status: string; state_revision: number }> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/restore-snapshot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await historyError(response, `/api/runs/${runId}/restore-snapshot`);
  return response.json();
}

export async function listRunExports(runId: string, signal?: AbortSignal): Promise<ExportReceipt[]> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/exports`, { signal });
  if (!response.ok) throw await historyError(response, `/api/runs/${runId}/exports`);
  const payload = await response.json() as { items?: unknown };
  return Array.isArray(payload.items)
    ? payload.items.map(normalizeExportReceipt).filter((item): item is ExportReceipt => Boolean(item))
    : [];
}

export async function downloadRunExportReceipt(
  runId: string,
  exportId: string,
  options: { signal?: AbortSignal; expectedSha256?: string; expectedSizeBytes?: number } = {},
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/exports/${encodeURIComponent(exportId)}`, { signal: options.signal });
  if (!response.ok) throw await historyError(response, `/api/runs/${runId}/exports/${exportId}`);
  const disposition = response.headers.get('content-disposition') ?? '';
  const blob = await response.blob();
  await verifyExportBlob(blob, {
    expectedSha256: options.expectedSha256,
    expectedSizeBytes: options.expectedSizeBytes,
    requireResponseSha256: true,
    responseSha256: response.headers.get('x-export-sha256') ?? '',
  });
  return {
    blob,
    filename: filenameFromDisposition(disposition, 'novel-export.bin'),
  };
}

function normalizeHistoryItem(value: unknown): RunHistoryItem {
  const item = value && typeof value === 'object' ? value as Partial<RunHistoryItem> : {};
  const stage: Partial<RunHistoryItem['current_stage']> = item.current_stage && typeof item.current_stage === 'object' ? item.current_stage : {};
  const status = item.status;
  const validStatuses = ['created', 'running', 'paused', 'awaiting_confirmation', 'recovery_required', 'failed', 'completed'] as const;
  return {
    run_id: String(item.run_id || ''),
    project_id: String(item.project_id || ''),
    title: String(item.title || '未命名小说'),
    quality_mode: item.quality_mode === 'fast' || item.quality_mode === 'deep' ? item.quality_mode : 'balanced',
    status: validStatuses.includes(status as typeof validStatuses[number]) ? status as RunHistoryItem['status'] : 'created',
    current_stage: {
      id: String(stage.id || ''),
      label: String(stage.label || ''),
      type: String(stage.type || '') as RunHistoryItem['current_stage']['type'],
    },
    completed_stage_ids: Array.isArray(item.completed_stage_ids) ? item.completed_stage_ids.map(String) : [],
    created_at: String(item.created_at || ''),
    updated_at: String(item.updated_at || ''),
    completed_at: String(item.completed_at || ''),
    words: Number(item.words || 0),
    total_tokens: Number(item.total_tokens || 0),
    estimated_cost_usd: Number(item.estimated_cost_usd || 0),
    summary: String(item.summary || ''),
    can_resume: Boolean(item.can_resume),
    recovery_required: Boolean(item.recovery_required),
    latest_snapshot_id: String(item.latest_snapshot_id || ''),
    export_ready: Boolean(item.export_ready),
    export_count: Number(item.export_count || 0),
    latest_export: normalizeExportReceipt(item.latest_export),
    state_revision: Number(item.state_revision || 0),
    source: 'server',
  };
}

function normalizeExportReceipt(value: unknown): ExportReceipt | null {
  if (!value || typeof value !== 'object') return null;
  const receipt = value as Partial<ExportReceipt>;
  const format = receipt.format === 'json' || receipt.format === 'zip' ? receipt.format : 'md';
  return {
    export_id: String(receipt.export_id || ''),
    run_id: String(receipt.run_id || ''),
    request_id: String(receipt.request_id || ''),
    schema_version: Number(receipt.schema_version || 1),
    version: Number(receipt.version || 0),
    snapshot_id: String(receipt.snapshot_id || ''),
    artifact_signature: String(receipt.artifact_signature || ''),
    selection_digest: String(receipt.selection_digest || ''),
    selection_snapshot: normalizeExportSelection(receipt.selection_snapshot),
    source_state_revision: Number(receipt.source_state_revision || 0),
    source_state_digest: String(receipt.source_state_digest || ''),
    format,
    chapter_ids: Array.isArray(receipt.chapter_ids) ? receipt.chapter_ids.map(String) : [],
    metadata: normalizeExportMetadata(receipt.metadata),
    filename: String(receipt.filename || `novel-export.${format}`),
    size_bytes: Number(receipt.size_bytes || 0),
    sha256: String(receipt.sha256 || ''),
    files: normalizeExportFiles(receipt.files),
    cover_asset: normalizeExportCoverAsset(receipt.cover_asset),
    created_at: String(receipt.created_at || ''),
  };
}

function normalizeExportSelection(value: unknown): ExportReceipt['selection_snapshot'] {
  if (!value || typeof value !== 'object') return null;
  const selection = value as Partial<NonNullable<ExportReceipt['selection_snapshot']>>;
  const format = selection.format === 'json' || selection.format === 'zip' ? selection.format : 'md';
  const sourceDigests = selection.source_artifact_digests && typeof selection.source_artifact_digests === 'object'
    ? Object.fromEntries(Object.entries(selection.source_artifact_digests).map(([key, digest]) => [key, String(digest || '')]))
    : {};
  const validation = selection.validation && typeof selection.validation === 'object'
    ? Object.fromEntries(Object.entries(selection.validation).map(([key, status]) => [key, String(status || '')]))
    : {};
  return {
    schema_version: Number(selection.schema_version || 1),
    format,
    chapter_ids: Array.isArray(selection.chapter_ids) ? selection.chapter_ids.map(String) : [],
    chapters: Array.isArray(selection.chapters) ? selection.chapters.map((chapter) => ({
      id: String(chapter?.id || ''),
      title: String(chapter?.title || ''),
      words: Number(chapter?.words || 0),
      content_sha256: String(chapter?.content_sha256 || ''),
    })) : [],
    metadata: normalizeExportMetadata(selection.metadata),
    cover_asset: normalizeExportCoverAsset(selection.cover_asset) ?? emptyCoverAsset(),
    validation,
    source_artifact_digests: sourceDigests,
    quality_digest: String(selection.quality_digest || ''),
    canon_digest: String(selection.canon_digest || ''),
  };
}

function normalizeExportFiles(value: unknown): ExportReceipt['files'] {
  if (!Array.isArray(value)) return [];
  return value.filter((item) => item && typeof item === 'object').map((item) => {
    const file = item as Partial<ExportReceipt['files'][number]>;
    return {
      path: String(file.path || ''),
      scope: file.scope === 'archive' ? 'archive' : 'package',
      media_type: String(file.media_type || 'application/octet-stream'),
      size_bytes: Number(file.size_bytes || 0),
      sha256: String(file.sha256 || ''),
    };
  });
}

function normalizeExportCoverAsset(value: unknown): ExportReceipt['cover_asset'] {
  if (!value || typeof value !== 'object') return null;
  const cover = value as Partial<NonNullable<ExportReceipt['cover_asset']>>;
  if (!cover.asset_id) return null;
  return {
    candidate_id: String(cover.candidate_id || ''),
    asset_id: String(cover.asset_id || ''),
    sha256: String(cover.sha256 || ''),
    mime_type: String(cover.mime_type || ''),
    width: Number(cover.width || 0),
    height: Number(cover.height || 0),
    size_bytes: Number(cover.size_bytes || 0),
    image_url: String(cover.image_url || ''),
  };
}

function emptyCoverAsset(): NonNullable<ExportReceipt['cover_asset']> {
  return { candidate_id: '', asset_id: '', sha256: '', mime_type: '', width: 0, height: 0, size_bytes: 0, image_url: '' };
}

function normalizeExportMetadata(value: unknown): ExportReceipt['metadata'] {
  const metadata = value && typeof value === 'object' ? value as Partial<ExportReceipt['metadata']> : {};
  return {
    author: String(metadata.author || ''),
    bundle_name: String(metadata.bundle_name || ''),
    title: String(metadata.title || ''),
    version_note: String(metadata.version_note || ''),
  };
}

async function historyError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    detail = '';
  }
  return new RunApiError(detail || `Request failed: ${url} ${response.status}`, response.status);
}

function filenameFromDisposition(value: string, fallback: string) {
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return fallback;
    }
  }
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback;
}
