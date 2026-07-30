import type { ChapterModelReview, ModelReviewDimension, QualityMode, RunEvent } from '../contracts';

/**
 * Deep/balanced 档模型评审展示模型（Phase 10.3c）。
 * 数据优先取章节产物的 `model_review`（10.4a additive 字段），回退运行事件
 * `model_review_completed` / `model_review_unavailable`；fast 档与旧 Run 完全缺失，
 * 由调用方按缺失态处理——不伪造分数、不渲染禁用壳。
 */
export function modelReviewForChapter(raw: unknown, events: RunEvent[], chapter: string): ChapterModelReview | null {
  const saved = normalizeModelReview(raw);
  if (saved) return saved;
  const event = events.find(
    (item) => (item.type === 'model_review_completed' || item.type === 'model_review_unavailable') && item.chapter === chapter,
  );
  if (!event) return null;
  if (event.type === 'model_review_unavailable') {
    return { status: 'unavailable', chapter, error: String(event.reason ?? event.error ?? '') };
  }
  return normalizeModelReview(event.model_review);
}

export function normalizeModelReview(value: unknown): ChapterModelReview | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (record.status !== 'completed' && record.status !== 'unavailable') return null;
  const dimensions = Array.isArray(record.dimensions)
    ? record.dimensions
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
      .map((item): ModelReviewDimension => ({
        dimension: String(item.dimension ?? '').trim() || '综合',
        score: clampScore(Number(item.score)),
        evidence: String(item.evidence ?? '').trim(),
        revision_instruction: String(item.revision_instruction ?? '').trim(),
      }))
    : [];
  return {
    status: record.status,
    chapter: String(record.chapter ?? ''),
    chapter_version: Number.isFinite(Number(record.chapter_version)) ? Number(record.chapter_version) : 0,
    dimensions,
    overall_score: clampScore(Number(record.overall_score)),
    tension: tensionOf(record.tension),
    voice: voiceOf(record.voice),
    error: String(record.error ?? ''),
    source: String(record.source ?? 'model_review'),
  };
}

/** fast 档无模型评审（成本合同），整个分区不渲染——不显示禁用壳。 */
export function showModelReviewSection(qualityMode: QualityMode): boolean {
  return qualityMode !== 'fast';
}

/** unavailable 的 reason 映射为作家语言；原始错误保留给调用方展示为溯源信息。 */
export function modelReviewUnavailableText(error: string): string {
  const raw = error.toLowerCase();
  if (/budget|预算|exceeded/.test(raw)) return '评审预算已用完，本章跳过了模型评审';
  if (/validation|schema|parse|json/.test(raw)) return '评审模型的输出未通过结构检查，本章评审按不可用处理';
  if (/timeout|timed out|超时/.test(raw)) return '评审模型响应超时，本章评审未能完成';
  if (/provider|connection|network|api|auth|key/.test(raw)) return '评审模型调用失败，本章评审未能完成';
  return '评审服务暂时不可用，本章未生成模型评审';
}

function tensionOf(value: unknown): ChapterModelReview['tension'] {
  if (!value || typeof value !== 'object') return { score: 0, basis: '' };
  const record = value as Record<string, unknown>;
  return { score: clampScore(Number(record.score)), basis: String(record.basis ?? '') };
}

function voiceOf(value: unknown): ChapterModelReview['voice'] {
  if (!value || typeof value !== 'object') return { drift: false, notes: '' };
  const record = value as Record<string, unknown>;
  return { drift: Boolean(record.drift), notes: String(record.notes ?? '') };
}

function clampScore(score: number) {
  return Number.isFinite(score) ? Math.min(10, Math.max(0, score)) : 0;
}
