import type {
  ExportReceipt,
  RunHistoryItem,
  RunHistoryResponse,
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
  const payload = await response.json();
  if (!isRecord(payload) || !Array.isArray(payload.items) || typeof payload.next_cursor !== 'string') {
    throw new RunApiError('Run history response does not match the vNext contract', 502);
  }
  return { items: payload.items.map(requireHistoryItem), next_cursor: payload.next_cursor };
}

export async function listRunExports(runId: string, signal?: AbortSignal): Promise<ExportReceipt[]> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/exports`, { signal });
  if (!response.ok) throw await historyError(response, `/api/runs/${runId}/exports`);
  const payload = await response.json();
  if (!isRecord(payload) || !Array.isArray(payload.items)) {
    throw new RunApiError('Export list response does not match the vNext contract', 502);
  }
  return payload.items.map(requireExportReceipt);
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
    filename: filenameFromDisposition(disposition),
  };
}

function requireHistoryItem(value: unknown): RunHistoryItem {
  const validStatuses = ['created', 'running', 'awaiting_decision', 'failed', 'completed', 'cancelled'] as const;
  const stages = ['info', 'characters', 'summary', 'outline', 'detail', 'text', 'cover', 'export', ''] as const;
  if (!isRecord(value) || !isRecord(value.current_stage)) return invalidHistory();
  if (!requiredStrings(value, ['run_id', 'project_id', 'title', 'created_at', 'updated_at', 'completed_at', 'summary', 'checkpoint_id'])) return invalidHistory();
  if (!requiredStrings(value.current_stage, ['id', 'label', 'type'])) return invalidHistory();
  if (!['fast', 'balanced', 'deep'].includes(String(value.quality_mode))) return invalidHistory();
  if (!validStatuses.includes(value.status as typeof validStatuses[number])) return invalidHistory();
  if (!stages.includes(value.current_stage.type as typeof stages[number])) return invalidHistory();
  if (!isStringArray(value.completed_stage_ids)) return invalidHistory();
  if (!requiredNumbers(value, ['words', 'total_tokens', 'export_count'])) return invalidHistory();
  if (value.estimated_cost_usd !== null && (
    typeof value.estimated_cost_usd !== 'number'
    || !Number.isFinite(value.estimated_cost_usd)
  )) return invalidHistory();
  if (typeof value.can_branch !== 'boolean' || typeof value.export_ready !== 'boolean') return invalidHistory();
  if (value.latest_export !== null) requireExportReceipt(value.latest_export);
  return { ...value, source: 'server' } as RunHistoryItem;
}

function requireExportReceipt(value: unknown): ExportReceipt {
  if (!isRecord(value) || !isRecord(value.metadata)) return invalidExport();
  if (!requiredStrings(value, ['export_id', 'run_id', 'artifact_id', 'artifact_signature', 'cover_asset_id', 'filename', 'media_type', 'sha256', 'created_at'])) return invalidExport();
  if (!requiredStrings(value.metadata, ['title', 'author', 'version_note'])) return invalidExport();
  if (!['md', 'json', 'zip'].includes(String(value.format))) return invalidExport();
  if (!isStringArray(value.chapter_version_ids) || typeof value.size_bytes !== 'number' || !Number.isFinite(value.size_bytes)) return invalidExport();
  return value as ExportReceipt;
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

function filenameFromDisposition(value: string) {
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      throw new RunApiError('Export filename is not valid UTF-8', 502);
    }
  }
  const plain = value.match(/filename="?([^";]+)"?/i)?.[1];
  if (!plain) throw new RunApiError('Export response is missing a filename', 502);
  return plain;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function requiredStrings(value: Record<string, unknown>, keys: string[]) {
  return keys.every((key) => typeof value[key] === 'string');
}

function requiredNumbers(value: Record<string, unknown>, keys: string[]) {
  return keys.every((key) => typeof value[key] === 'number' && Number.isFinite(value[key]));
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function invalidHistory(): never {
  throw new RunApiError('Run history item does not match the vNext contract', 502);
}

function invalidExport(): never {
  throw new RunApiError('Export receipt does not match the vNext contract', 502);
}
