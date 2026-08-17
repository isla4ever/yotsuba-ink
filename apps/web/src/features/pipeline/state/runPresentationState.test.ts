import { describe, expect, it } from 'vitest';
import { modeRoutePolicy, runActionPresentation } from './runPresentationState';

const base = {
  approvalPending: false,
  checkpointContinueReady: true,
  briefContinueReady: false,
  qualityMode: 'deep' as const,
  runControlState: 'running' as const,
  running: false,
  selectedStageCheckpointReady: true,
  selectedStageStatus: 'done' as const,
  selectedStageType: 'spine' as const,
  transitioning: false,
  workspacePhase: 'running' as const,
};

describe('runActionPresentation delivery gates', () => {
  it('keeps ordinary delivery-ready stages on the continue action', () => {
    expect(runActionPresentation(base)).toMatchObject({ key: 'continue', disabled: false });
  });

  it('blocks Cover continuation while the real image asset still needs attention', () => {
    expect(runActionPresentation({
      ...base,
      selectedStageStatus: 'attention',
      selectedStageType: 'cover',
    })).toMatchObject({ key: 'awaiting-confirmation', label: '等待封面资产', disabled: true });
  });

  it('blocks Export return while any delivery gate still needs attention', () => {
    expect(runActionPresentation({
      ...base,
      selectedStageStatus: 'attention',
      selectedStageType: 'export',
    })).toMatchObject({ key: 'awaiting-confirmation', label: '等待导出就绪', disabled: true });
  });

  it('projects balanced LangGraph interrupts as stage decisions', () => {
    expect(runActionPresentation({
      ...base,
      approvalPending: true,
      checkpointContinueReady: false,
      qualityMode: 'balanced',
      selectedStageCheckpointReady: false,
    })).toMatchObject({ key: 'awaiting-confirmation', label: '等待阶段定稿', disabled: true });
  });

  it('routes the Brief settlement to the story spine', () => {
    expect(runActionPresentation({
      ...base,
      checkpointContinueReady: false,
      briefContinueReady: true,
      selectedStageType: 'brief',
    })).toMatchObject({ key: 'continue', label: '继续进入故事脊柱' });
  });

  it('finishes Export without returning to planning', () => {
    expect(runActionPresentation({
      ...base,
      selectedStageType: 'export',
    })).toMatchObject({ key: 'complete', label: '完成本次创作' });
  });
});

describe('modeRoutePolicy', () => {
  it('keeps all stage routes available for balanced and deep modes', () => {
    expect(modeRoutePolicy('balanced').stageRoutes).toBe('all');
    expect(modeRoutePolicy('balanced')).toEqual({ stageRoutes: 'all', monitor: 'available' });
    expect(modeRoutePolicy('deep').stageRoutes).toBe('all');
  });

  it('keeps fast mode on the run monitor without a planning surface', () => {
    expect(modeRoutePolicy('fast')).toEqual({ stageRoutes: 'none', monitor: 'default' });
  });

  it('differentiates monitor console availability per mode', () => {
    expect(modeRoutePolicy('fast').monitor).toBe('default');
    expect(modeRoutePolicy('balanced').monitor).toBe('available');
    expect(modeRoutePolicy('deep').monitor).toBe('none');
  });
});
