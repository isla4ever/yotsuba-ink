import type { RunEvent } from '../contracts';

/**
 * Phase 12 D4: aggregated "第 N/M 阶段" position derived from real run facts
 * (`node_completed` events → completed stage ids) — never from timers.
 */
export type StagePositionSummary = {
  /** 1-based position of the current stage in the workflow (0 when unknown). */
  current: number;
  total: number;
  completed: number;
};

export function stagePositionSummary(params: {
  completedStageIds: string[];
  currentStageId: string;
  stageIds: string[];
}): StagePositionSummary {
  const completed = params.completedStageIds.filter((id) => params.stageIds.includes(id));
  const index = params.stageIds.indexOf(params.currentStageId);
  return {
    completed: completed.length,
    current: index < 0 ? 0 : index + 1,
    total: params.stageIds.length,
  };
}

export function stagePositionEqual(left: StagePositionSummary, right: StagePositionSummary): boolean {
  return left.completed === right.completed && left.current === right.current && left.total === right.total;
}

/** Unique stage ids with a `node_completed` event (newest-first input list). */
export function completedStageIdsFromEvents(events: RunEvent[]): string[] {
  const ids: string[] = [];
  for (const event of events) {
    if (event.type !== 'node_completed' || !event.node_id) continue;
    if (!ids.includes(event.node_id)) ids.push(event.node_id);
  }
  return ids;
}
