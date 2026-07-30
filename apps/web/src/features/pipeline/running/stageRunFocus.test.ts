import { describe, expect, it } from 'vitest';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { latestDraftRegenerationFailure, shouldFocusDraftCandidates, shouldFocusVariants } from './stageRunFocus';

describe('stage run focus', () => {
  it('opens balanced comparison only after a request and two generated variants', () => {
    const events = [
      runEvent('variant_generated'),
      runEvent('variant_generated'),
      runEvent('variant_compare_requested'),
    ];

    expect(shouldFocusVariants(stage(), events, workflow('balanced'))).toBe(true);
    expect(shouldFocusVariants(stage(), events, workflow('fast'))).toBe(false);
    expect(shouldFocusVariants(stage(), events.slice(0, 2), workflow('balanced'))).toBe(false);
  });

  it('closes balanced comparison after a variant is selected', () => {
    const events = [
      runEvent('best_variant_selected'),
      runEvent('variant_generated'),
      runEvent('variant_generated'),
      runEvent('variant_compare_requested'),
    ];

    expect(shouldFocusVariants(stage(), events, workflow('balanced'))).toBe(false);
  });

  it('keeps deep draft comparison open until selection or confirmation', () => {
    const requested = [runEvent('draft_regeneration_requested')];
    expect(shouldFocusDraftCandidates(stage(), requested, workflow('deep'))).toBe(true);

    const selectedAfterRequest = [runEvent('draft_candidate_selected'), ...requested];
    expect(shouldFocusDraftCandidates(stage(), selectedAfterRequest, workflow('deep'))).toBe(false);

    const confirmed = [runEvent('stage_artifact_confirmed'), ...requested];
    expect(shouldFocusDraftCandidates(stage(), confirmed, workflow('deep'))).toBe(false);
  });

  it('uses the same manual candidate focus for the balanced Info gate', () => {
    const infoStage = stage('info_recommend');
    const requested = [{ ...runEvent('draft_regeneration_requested'), node_id: 'info' }];

    expect(shouldFocusDraftCandidates(infoStage, requested, workflow('balanced'))).toBe(true);
    expect(shouldFocusDraftCandidates(infoStage, requested, workflow('fast'))).toBe(false);
    expect(shouldFocusDraftCandidates(infoStage, [
      { ...runEvent('draft_regeneration_failed'), node_id: 'info' },
      ...requested,
    ], workflow('balanced'))).toBe(false);
  });

  it('ignores a delayed failure from an older candidate request', () => {
    const infoStage = stage('info_recommend');
    const events = [
      { ...runEvent('draft_regeneration_failed'), node_id: 'info', request_id: 'request-1' },
      { ...runEvent('draft_regeneration_requested'), node_id: 'info', request_id: 'request-2' },
      { ...runEvent('draft_regeneration_requested'), node_id: 'info', request_id: 'request-1' },
    ];

    expect(shouldFocusDraftCandidates(infoStage, events, workflow('balanced'))).toBe(true);
    expect(latestDraftRegenerationFailure('info', events)).toBeNull();
  });

  it('returns the failure belonging to the latest candidate request', () => {
    const events = [
      { ...runEvent('draft_regeneration_failed'), node_id: 'info', request_id: 'request-2', error: 'provider unavailable' },
      { ...runEvent('draft_regeneration_requested'), node_id: 'info', request_id: 'request-2' },
      { ...runEvent('draft_regeneration_failed'), node_id: 'info', request_id: 'request-1' },
      { ...runEvent('draft_regeneration_requested'), node_id: 'info', request_id: 'request-1' },
    ];

    expect(latestDraftRegenerationFailure('info', events)?.error).toBe('provider unavailable');
  });
});

function runEvent(type: string): RunEvent {
  return { type, run_id: 'run-1', node_id: 'summary' };
}

function stage(type: WorkflowStage['type'] = 'summary'): WorkflowStage {
  return {
    id: type === 'info_recommend' ? 'info' : 'summary',
    type,
    label: type === 'info_recommend' ? '创作立项定稿' : '全书梗概',
    params: {},
    input_refs: [],
    output_key: 'summary',
    memory_policy: { read: true, write: true, scope: 'project', kinds: [] },
    provider_profile_id: 'provider',
    model_settings: { model: 'model', temperature: 0.7, max_tokens: 1000, top_p: 1, timeout_seconds: 60 },
    prompt_template_id: 'prompt-summary',
    input_schema: [],
    output_schema: {},
    quality_policy: { min_score: 0.8, retry_on_fail: true, require_human_review: false, checks: [] },
    variant_policy: { enabled: true, candidate_count: 2, judge_provider_profile_id: 'inherit', judge_model: 'model', dimensions: [], retry_on_fail: false },
  };
}

function workflow(qualityMode: WorkflowDefinition['quality_mode']): WorkflowDefinition {
  return {
    id: 'workflow',
    name: 'Workflow',
    version: '1',
    global_inputs: [],
    provider_profiles: [],
    prompt_templates: [],
    stage_configs: {},
    batch_policy: { enabled: false, count: 1, parallelism: 1 },
    quality_mode: qualityMode,
    nodes: [stage()],
    edges: [],
  };
}
