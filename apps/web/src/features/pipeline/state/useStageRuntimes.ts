import { useRef } from 'react';
import type { WorkflowStage } from '../contracts';
import type { StageRuntimeSummaryMap } from './pipelineShellContext';
import {
  indexedStageCheckpointReady,
  type RunEventIndex,
} from './runEventIndex';
import { stageDeliveryStatus } from './stageDeliveryStatus';

/** Pure derivation: per-stage runtime summary from the event index (F5/F6). */
export function stageRuntimeSummaryMap(
  index: RunEventIndex,
  stages: Array<Pick<WorkflowStage, 'id' | 'type'>>,
): StageRuntimeSummaryMap {
  const map: StageRuntimeSummaryMap = {};
  for (const stage of stages) {
    map[stage.id] = {
      checkpointReady: indexedStageCheckpointReady(index, stage.id),
      status: stageDeliveryStatus(index, stage),
    };
  }
  return map;
}

export function stageRuntimesEqual(left: StageRuntimeSummaryMap, right: StageRuntimeSummaryMap): boolean {
  const leftIds = Object.keys(left);
  if (leftIds.length !== Object.keys(right).length) return false;
  return leftIds.every((id) => (
    right[id]
    && left[id].status === right[id].status
    && left[id].checkpointReady === right[id].checkpointReady
  ));
}

/**
 * Value-stable stage runtime summary: recomputed per event, but the returned
 * reference only changes when a stage status/checkpoint actually flips — so
 * the shell RunState slice stays referentially stable during delta streaming.
 */
export function useStageRuntimes(
  index: RunEventIndex,
  stages: Array<Pick<WorkflowStage, 'id' | 'type'>>,
): StageRuntimeSummaryMap {
  const previous = useRef<StageRuntimeSummaryMap | null>(null);
  const next = stageRuntimeSummaryMap(index, stages);
  if (previous.current && stageRuntimesEqual(previous.current, next)) return previous.current;
  previous.current = next;
  return next;
}
