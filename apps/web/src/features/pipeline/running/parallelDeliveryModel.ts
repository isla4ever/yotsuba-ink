import type { RunEvent } from '../contracts';
import { coverArtifact, type CoverArtifact } from './coverArtifact';
import { coverImageSource } from './coverPresentation';
import type { WritingArtifact } from './writingArtifactModel';

export type DeliveryGateState = 'ready' | 'pending' | 'checking';

export type ParallelDeliverySnapshot = {
  cover: CoverArtifact;
  coverReady: number;
  coverTotal: number;
  finalGates: Array<{ key: string; label: string; detail: string; state: DeliveryGateState }>;
  message: string;
  status: 'idle' | 'running' | 'ready' | 'degraded' | 'cancelled';
};

const PARALLEL_EVENT_TYPES = new Set([
  'parallel_delivery_started',
  'parallel_delivery_ready',
  'parallel_delivery_degraded',
]);

export function parallelDeliverySnapshot(events: RunEvent[], writing: WritingArtifact): ParallelDeliverySnapshot {
  const lifecycle = lastMatchingEvent(events, (event) => PARALLEL_EVENT_TYPES.has(event.type));
  const coverEvent = lastMatchingEvent(events, (event) => event.node_type === 'cover_image' && Boolean(event.artifact));
  const cover = coverArtifact(JSON.stringify(coverEvent?.artifact ?? {}));
  const delivery = lifecycle?.parallel_delivery;
  const status = lifecycle?.type === 'parallel_delivery_ready'
    ? 'ready'
    : lifecycle?.type === 'parallel_delivery_degraded'
      ? 'degraded'
      : lifecycle?.type === 'parallel_delivery_started'
        ? 'running'
        : delivery?.status ?? 'idle';
  const readableReadyCount = cover.candidates.filter(
    (item) => item.asset_status === 'ready' && Boolean(coverImageSource(item.image_url)),
  ).length;
  const coverReady = cover.candidates.length
    ? readableReadyCount
    : cover.asset_generation.ready_count || delivery?.ready_count || 0;
  const coverTotal = cover.asset_generation.total || delivery?.total || cover.candidates.length;
  const completed = writing.chapters.filter((chapter) => chapter.status === 'completed' && chapter.content.trim());
  const allChaptersReady = completed.length >= writing.target_chapters;
  const formalCover = cover.candidates.find((candidate) => candidate.id === cover.selected_candidate_id);
  const formalCoverReady = formalCover?.asset_status === 'ready' && Boolean(coverImageSource(formalCover.image_url));
  const qualityObserved = completed.length > 0 && completed.every((chapter) => Boolean(chapter.quality_recheck));
  const qualityReady = qualityObserved && completed.every((chapter) => chapter.quality_recheck?.status === 'passed');
  const canonEvent = events.find((event) => Array.isArray(event.pending_conflicts));
  const canonObserved = Boolean(canonEvent);
  const canonReady = canonObserved && (canonEvent?.pending_conflicts?.length ?? 0) === 0;

  return {
    cover,
    coverReady,
    coverTotal,
    finalGates: [
      {
        key: 'chapters',
        label: '目标章节全部完成',
        detail: `${completed.length}/${writing.target_chapters} 章正文非空`,
        state: allChaptersReady ? 'ready' : 'pending',
      },
      {
        key: 'cover',
        label: '正式封面已选择',
        detail: formalCoverReady ? '真实图片资产可读取' : '可先生成候选，稍后完成正式选择',
        state: formalCoverReady ? 'ready' : 'pending',
      },
      {
        key: 'quality',
        label: '最新质量检查通过',
        detail: qualityObserved ? `${completed.length} 章已取得版本绑定复检` : '正式交付时按最新正文版本重算',
        state: qualityReady ? 'ready' : qualityObserved ? 'pending' : 'checking',
      },
      {
        key: 'canon',
        label: 'Canon 无未决冲突',
        detail: canonObserved ? `${canonEvent?.pending_conflicts?.length ?? 0} 项未决冲突` : '正式交付时读取事实账本校验',
        state: canonReady ? 'ready' : canonObserved ? 'pending' : 'checking',
      },
    ],
    message: lifecycle?.message || '细纲定稿后，正文创作与封面、预览交付并行推进。',
    status,
  };
}

function lastMatchingEvent(events: RunEvent[], predicate: (event: RunEvent) => boolean) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event && predicate(event)) return event;
  }
  return undefined;
}
