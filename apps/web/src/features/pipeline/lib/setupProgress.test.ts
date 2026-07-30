import { describe, expect, it } from 'vitest';
import type { KnowledgeDocument, ProviderReadinessReport, WorkflowDefinition } from '../contracts';
import { defaultWorkflow } from '../state/defaultWorkflow';
import {
  buildSettingsSections,
  buildSetupSteps,
  firstBlockingSetupTarget,
  providerReadinessSummary,
  reviewCreationModeCardId,
  reviewReferenceCardId,
  shouldShowGuidedSetup,
} from './setupProgress';

const readyReport: ProviderReadinessReport = {
  ok: true,
  scope: 'configuration_only',
  checked_provider_count: 2,
  checks: [
    { provider_id: 'openai-compatible', provider_name: '文本服务', expected_kind: 'openai-compatible', used_by: ['创作立项'], ready: true, issue_codes: [], message: '配置完整' },
    { provider_id: 'openai-compatible-image', provider_name: '封面服务', expected_kind: 'openai-compatible-image', used_by: ['封面'], ready: true, issue_codes: [], message: '配置完整' },
  ],
  message: 'ready',
};

describe('setup progress derivation (Phase 12 A4 three-step flow)', () => {
  it('derives the three-step flow 故事起点/连接 AI 服务/确认启动 without a detached completion flag', () => {
    const steps = buildSetupSteps({ workflow: defaultWorkflow, knowledgeDocuments: [], readiness: readyReport });

    expect(steps.map((step) => step.id)).toEqual(['story', 'ai-service', 'review']);
    expect(steps.map((step) => step.label)).toEqual(['故事起点', '连接 AI 服务', '确认启动']);
    expect(steps.every((step) => step.status === 'complete')).toBe(true);
    // The complete review step summarizes the applied defaults for the nav rail.
    expect(steps[2].summary).toContain('智能参考');
    expect(steps[2].summary).toContain('平衡');
    expect(shouldShowGuidedSetup(steps)).toBe(false);
  });

  it('targets the first missing story field before later readiness issues', () => {
    const workflow = updateInfoField(defaultWorkflow, 'core_concept', '');
    const steps = buildSetupSteps({ workflow, knowledgeDocuments: [], readiness: undefined });

    expect(firstBlockingSetupTarget(steps)).toEqual({ stepId: 'story', fieldId: 'setup-story-core_concept' });
    expect(steps.find((step) => step.id === 'ai-service')?.status).toBe('blocked');
    // Earlier blocking issues also block the launch step so 确认启动 cannot pass.
    expect(steps.find((step) => step.id === 'review')?.status).toBe('blocked');
  });

  it('blocks the story step and forces guided setup for a project workflow with cleared narrative seeds', () => {
    // Phase 12 M1: project creation blanks demo story seeds server-side; this
    // mirrors that copy and guards hasConfiguredValue against regressions.
    const steps = buildSetupSteps({ workflow: clearNarrativeSeeds(defaultWorkflow), knowledgeDocuments: [], readiness: readyReport });

    const story = steps.find((step) => step.id === 'story');
    expect(story?.status).toBe('blocked');
    expect(story?.issues.map((issue) => issue.code)).toEqual([
      'story_audience_missing',
      'story_core_concept_missing',
      'story_keywords_missing',
      'story_taboos_missing',
    ]);
    expect(firstBlockingSetupTarget(steps)).toEqual({ stepId: 'story', fieldId: 'setup-story-audience' });
    expect(shouldShowGuidedSetup(steps)).toBe(true);
  });

  it('re-homes reference issues to the review step anchored on the reference card', () => {
    let workflow = updateInfoField(defaultWorkflow, 'reference_mode', 'knowledge_base');
    workflow = updateInfoField(workflow, 'knowledge_base_doc_ids', ['missing-doc']);
    const documents: KnowledgeDocument[] = [{
      doc_id: 'ready-doc', title: 'Ready', filename: 'ready.md', chunk_count: 1,
      status: 'ready', parser: 'text', preview: '',
    }];
    const steps = buildSetupSteps({ workflow, knowledgeDocuments: documents, readiness: readyReport });

    const review = steps.find((step) => step.id === 'review');
    expect(review?.issues[0].code).toBe('knowledge_document_unavailable');
    expect(review?.issues[0].target).toEqual({ stepId: 'review', fieldId: reviewReferenceCardId });
    // Story and service stay complete: the reference problem belongs to the launch page.
    expect(steps.find((step) => step.id === 'story')?.status).toBe('complete');
    expect(steps.find((step) => step.id === 'ai-service')?.status).toBe('complete');
    expect(shouldShowGuidedSetup(steps)).toBe(true);
  });

  it('re-homes an invalid creation mode to the review step anchored on the mode card', () => {
    const workflow = { ...defaultWorkflow, quality_mode: 'legacy' as WorkflowDefinition['quality_mode'] };
    const steps = buildSetupSteps({ workflow, knowledgeDocuments: [], readiness: readyReport });

    expect(firstBlockingSetupTarget(steps)).toEqual({ stepId: 'review', fieldId: reviewCreationModeCardId });
    expect(steps.find((step) => step.id === 'review')?.summary).toBe('1 项需要处理');
  });

  it('keeps reference warnings non-blocking so launch stays available', () => {
    const workflow = updateInfoField(defaultWorkflow, 'reference_mode', 'url');
    const steps = buildSetupSteps({ workflow, knowledgeDocuments: [], readiness: readyReport });

    const review = steps.find((step) => step.id === 'review');
    expect(review?.issues.map((issue) => issue.code)).toEqual(['reference_url_empty']);
    expect(review?.status).toBe('complete');
    expect(shouldShowGuidedSetup(steps)).toBe(false);
  });

  it('reports setup truth as concise settings sections', () => {
    const sections = buildSettingsSections({ workflow: defaultWorkflow, knowledgeDocuments: [], readiness: readyReport });

    expect(sections.map((section) => section.id)).toEqual(['story', 'references', 'creation-mode', 'ai-service']);
    expect(sections.find((section) => section.id === 'ai-service')?.status).toBe('ready');
    expect(sections.find((section) => section.id === 'references')?.status).toBe('ready');
    expect(sections.find((section) => section.id === 'creation-mode')?.status).toBe('ready');
  });

  it('derives a successful service label when the API message is intentionally empty', () => {
    expect(providerReadinessSummary({ ...readyReport, message: '' })).toBe('2 项服务检查通过');
  });
});

/** Mirrors backend seed_policy.scrub_narrative_seeds for the info-stage and global narrative fields. */
function clearNarrativeSeeds(workflow: WorkflowDefinition): WorkflowDefinition {
  const seedKeys = ['audience', 'core_concept', 'keywords', 'taboos', 'reference_keywords', 'reference_query_intent'];
  const blank = (field: WorkflowDefinition['global_inputs'][number]) =>
    ({ ...field, default: Array.isArray(field.default) ? [] : '' });
  return {
    ...workflow,
    global_inputs: workflow.global_inputs.map((field) => field.key === 'title' ? blank(field) : field),
    nodes: workflow.nodes.map((stage) => stage.id === 'info' ? {
      ...stage,
      input_schema: stage.input_schema.map((field) => seedKeys.includes(field.key) ? blank(field) : field),
    } : stage),
  };
}

function updateInfoField(workflow: WorkflowDefinition, key: string, value: unknown): WorkflowDefinition {
  return {
    ...workflow,
    nodes: workflow.nodes.map((stage) => stage.id === 'info' ? {
      ...stage,
      input_schema: stage.input_schema.map((field) => field.key === key ? { ...field, default: value } : field),
    } : stage),
  };
}
