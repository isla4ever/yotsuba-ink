import { describe, expect, it } from 'vitest';
import { modeRoutePolicy, runActionPresentation } from './runPresentationState';

const base = {
  approvalPending: false,
  checkpointContinueReady: true,
  infoContinueReady: false,
  qualityMode: 'deep' as const,
  runControlState: 'running' as const,
  running: false,
  selectedStageCheckpointReady: true,
  selectedStageStatus: 'done' as const,
  selectedStageType: 'summary' as const,
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

  it('routes the info settlement to the character bible', () => {
    expect(runActionPresentation({
      ...base,
      checkpointContinueReady: false,
      infoContinueReady: true,
      selectedStageType: 'info',
    })).toMatchObject({ key: 'continue', label: '继续进入人物圣经' });
  });
});

describe('modeRoutePolicy', () => {
  it('keeps all stage routes available for balanced and deep modes', () => {
    expect(modeRoutePolicy('balanced', false).stageRoutes).toBe('all');
    expect(modeRoutePolicy('balanced', true)).toEqual({ planningSurface: 'cockpit', stageRoutes: 'all' });
    expect(modeRoutePolicy('deep', false).stageRoutes).toBe('all');
  });

  it('keeps fast mode in its read-only cockpit projection', () => {
    expect(modeRoutePolicy('fast', true)).toEqual({ planningSurface: 'cockpit', stageRoutes: 'none' });
  });
});
