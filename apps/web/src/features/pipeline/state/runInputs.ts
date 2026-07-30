import type { ProjectRecord, RunInputs, WorkflowDefinition } from '../contracts';
import { controlModeForQuality } from '../lib/qualityModes';
import { executionModeForRunSource, type RunSource } from '../lib/runSource';
import { stageInputDefaults } from '../lib/workflow';

type RunProjectContext = Pick<ProjectRecord, 'id' | 'title'> | null;

function globalInputDefault(workflow: WorkflowDefinition, key: string): string {
  const value = workflow.global_inputs.find((item) => item.key === key)?.default;
  return value == null ? '' : String(value);
}

/**
 * Phase 11.2 (mine 4): title comes from the active project (falling back to
 * the workflow's own global_inputs default / name — never a hardcoded book
 * name), theme is derived from the Info-stage keywords, and project_id rides along
 * so the backend records real ownership instead of project_id == run_id.
 */
export function buildRunInputs(
  workflow: WorkflowDefinition,
  runSource: RunSource = 'backend',
  project: RunProjectContext = null,
): RunInputs {
  const stageConfigs = Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stageInputDefaults(stage)]));
  const infoConfig = stageConfigs.info ?? {};
  const textConfig = stageConfigs.text ?? {};
  const exportConfig = stageConfigs.export ?? {};
  const controlMode = controlModeForQuality(workflow.quality_mode);
  const title = project?.title?.trim() || globalInputDefault(workflow, 'title') || workflow.name;
  const theme = Array.isArray(infoConfig.keywords)
    ? infoConfig.keywords.map(String).filter(Boolean).join('、')
    : String(infoConfig.core_concept ?? '');
  return {
    title,
    theme,
    project_id: project?.id ?? '',
    quality_mode: workflow.quality_mode,
    execution_mode: executionModeForRunSource(runSource),
    run_intent: {
      project_brief: {
        title,
        theme,
        genre: infoConfig.genre,
        target_length: infoConfig.target_length,
        target_words_range: infoConfig.target_words_range,
        audience: infoConfig.audience,
        core_concept: infoConfig.core_concept,
        keywords: infoConfig.keywords,
        taboos: infoConfig.taboos,
      },
      knowledge_strategy: {
        reference_mode: infoConfig.reference_mode,
        reference_keywords: infoConfig.reference_keywords,
        reference_query_intent: infoConfig.reference_query_intent,
        reference_urls: infoConfig.reference_urls,
        knowledge_base_doc_ids: infoConfig.knowledge_base_doc_ids,
        enable_web_search: infoConfig.enable_web_search,
        reference_summary: infoConfig.reference_summary,
      },
      mode_policy: {
        quality_mode: workflow.quality_mode,
        control_mode: controlMode,
        checkpoint_stages: workflow.quality_mode === 'fast'
          ? []
          : workflow.quality_mode === 'balanced'
            ? ['info']
            : workflow.nodes.filter((stage) => stage.id !== 'export').map((stage) => stage.id),
      },
      variant_strategy: {
        enabled_stages: workflow.nodes.filter((stage) => stage.variant_policy.enabled).map((stage) => stage.id),
        text_compare_enabled: textConfig.enable_version_compare,
        candidate_count: textConfig.version_candidate_count,
        judge_provider_profile_id: textConfig.judge_provider_profile_id,
        judge_model: textConfig.judge_model,
        dimensions: textConfig.compare_dimensions,
      },
      export_preferences: {
        export_format: exportConfig.export_format,
        manual_return_required: workflow.quality_mode === 'deep',
      },
    },
    stage_configs: stageConfigs,
  };
}
