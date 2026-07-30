import { describe, expect, it } from 'vitest';
import { runActionPresentation } from './runPresentationState';

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
      selectedStageType: 'cover_image',
    })).toMatchObject({ key: 'awaiting-confirmation', label: '等待封面资产', disabled: true });
  });

  it('blocks Export return while any delivery gate still needs attention', () => {
    expect(runActionPresentation({
      ...base,
      selectedStageStatus: 'attention',
      selectedStageType: 'export_artifact',
    })).toMatchObject({ key: 'awaiting-confirmation', label: '等待导出就绪', disabled: true });
  });
});
