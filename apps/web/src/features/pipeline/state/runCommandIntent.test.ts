import { describe, expect, it } from 'vitest';
import { resolveRunCommandIntent } from './runCommandIntent';

type IntentParams = Parameters<typeof resolveRunCommandIntent>[0];

describe('run command intent', () => {
  it('keeps a busy fast run locked', () => {
    expect(resolveRunCommandIntent(context({
      activeRunId: 'fast-run',
      qualityMode: 'fast',
      runControlState: 'running',
      running: true,
      workspacePhase: 'running',
    }))).toEqual({ type: 'none' });
  });

  it('continues Info before considering pause or a new run', () => {
    expect(resolveRunCommandIntent(context({
      activeRunId: 'balanced-run',
      infoContinueReady: true,
      paused: true,
      workspacePhase: 'running',
    }))).toEqual({
      type: 'continue',
      stageId: 'info',
      fallbackNextStageId: 'summary',
    });
  });

  it('returns from Export instead of reopening the stream', () => {
    expect(resolveRunCommandIntent(context({
      activeRunId: 'deep-run',
      checkpointContinueReady: true,
      checkpointStageId: 'export',
      paused: true,
      qualityMode: 'deep',
      selectedStageType: 'export_artifact',
      workspacePhase: 'running',
    }))).toEqual({ type: 'return_export' });
  });

  it('does not resume a deep checkpoint before confirmation', () => {
    expect(resolveRunCommandIntent(context({
      activeRunId: 'deep-run',
      checkpointStageId: 'summary',
      paused: true,
      qualityMode: 'deep',
      workspacePhase: 'running',
    }))).toEqual({ type: 'none' });
  });

  it('resumes an ordinary safe pause and pauses an active balanced run', () => {
    expect(resolveRunCommandIntent(context({
      activeRunId: 'paused-run',
      paused: true,
      workspacePhase: 'running',
    }))).toEqual({ type: 'resume' });

    expect(resolveRunCommandIntent(context({
      activeRunId: 'running-run',
      runControlState: 'running',
      running: true,
      workspacePhase: 'running',
    }))).toEqual({ type: 'pause' });
  });

  it('starts only when no active command state takes precedence', () => {
    expect(resolveRunCommandIntent(context())).toEqual({ type: 'start' });
  });
});

function context(overrides: Partial<IntentParams> = {}): IntentParams {
  return {
    activeRunId: '',
    checkpointContinueReady: false,
    checkpointStageId: '',
    infoContinueReady: false,
    paused: false,
    qualityMode: 'balanced',
    runControlState: 'idle',
    running: false,
    selectedStageType: 'info_recommend',
    workspacePhase: 'planning',
    ...overrides,
  };
}
