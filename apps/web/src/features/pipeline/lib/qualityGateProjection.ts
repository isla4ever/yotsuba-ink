import type { RunEvent } from '../contracts';

export type ChapterCapacityProjection = {
  countingStandard: string;
  visibleChars: number;
  targetChars: number;
  softMinChars: number;
  softMaxChars: number;
  hardMinChars: number;
  hardMaxChars: number;
  status: 'hard_underflow' | 'soft_underflow' | 'within_soft' | 'soft_overflow' | 'hard_overflow';
};

export function latestChapterCapacity(events: RunEvent[]): ChapterCapacityProjection | undefined {
  const decisions = events
    .filter((event) => event.type === 'decision.required')
    .sort((left, right) => Number(right.sequence || 0) - Number(left.sequence || 0));
  for (const event of decisions) {
    const payload = record(event.payload);
    const reason = record(payload?.reason);
    const capacity = record(reason?.capacity);
    if (!capacity || !isCapacityStatus(capacity.status)) continue;
    const values = [
      capacity.visible_chars,
      capacity.target_chars,
      capacity.soft_min_chars,
      capacity.soft_max_chars,
      capacity.hard_min_chars,
      capacity.hard_max_chars,
    ];
    if (!values.every((value) => typeof value === 'number' && Number.isFinite(value))) continue;
    return {
      countingStandard: typeof capacity.counting_standard === 'string' ? capacity.counting_standard : '',
      visibleChars: capacity.visible_chars as number,
      targetChars: capacity.target_chars as number,
      softMinChars: capacity.soft_min_chars as number,
      softMaxChars: capacity.soft_max_chars as number,
      hardMinChars: capacity.hard_min_chars as number,
      hardMaxChars: capacity.hard_max_chars as number,
      status: capacity.status,
    };
  }
  return undefined;
}

export function chapterCapacitySummary(capacity: ChapterCapacityProjection): string {
  const statusLabel = {
    hard_underflow: '低于硬下限',
    soft_underflow: '低于软目标',
    within_soft: '位于软区间',
    soft_overflow: '高于软目标',
    hard_overflow: '超过硬上限',
  }[capacity.status];
  const range = capacity.status.startsWith('hard_')
    ? `硬区间 ${capacity.hardMinChars}-${capacity.hardMaxChars}`
    : `软区间 ${capacity.softMinChars}-${capacity.softMaxChars}`;
  return `${statusLabel} · ${capacity.visibleChars} / ${capacity.targetChars} 字 · ${range}`;
}

function record(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' ? value as Record<string, unknown> : undefined;
}

function isCapacityStatus(value: unknown): value is ChapterCapacityProjection['status'] {
  return [
    'hard_underflow',
    'soft_underflow',
    'within_soft',
    'soft_overflow',
    'hard_overflow',
  ].includes(String(value));
}
