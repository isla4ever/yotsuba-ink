import type { ProjectRecord, RunStartInputs, WorkflowDefinition } from '../contracts';
import type { RunSource } from '../lib/runSource';
import { lengthEnvelopeFromStage } from '../lib/narrativeScale';
import { stageInputDefaults } from '../lib/workflow';

type RunProjectContext = Pick<ProjectRecord, 'id' | 'title'> | null;

function globalInputDefault(workflow: WorkflowDefinition, key: string): string {
  const value = workflow.global_inputs.find((item) => item.key === key)?.default;
  return value == null ? '' : String(value);
}

function positiveInteger(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
}

/**
 * The title comes from the active project (falling back to
 * the workflow's own global_inputs default / name — never a hardcoded book
 * name), theme is derived from the Brief-stage keywords, and project_id rides along
 * so the backend records explicit project ownership.
 */
export function buildRunInputs(
  workflow: WorkflowDefinition,
  runSource: RunSource = 'backend',
  project: RunProjectContext = null,
): RunStartInputs {
  const stageConfigs = Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stageInputDefaults(stage)]));
  const briefStage = workflow.nodes.find((stage) => stage.type === 'brief');
  const briefConfig = briefStage ? { ...stageConfigs[briefStage.id] } : {};
  const lengthEnvelope = briefStage ? lengthEnvelopeFromStage(briefStage) : {
    word_target_soft: 100_000,
    chapter_target_soft: 50,
  };
  delete briefConfig.word_target_soft;
  delete briefConfig.chapter_target_soft;
  const scaleOverrides = {
    volume_target: positiveInteger(briefConfig.volume_target_override),
    turn_target: positiveInteger(briefConfig.turn_target_override),
    cast_demand_target: positiveInteger(briefConfig.cast_demand_override),
  };
  delete briefConfig.volume_target_override;
  delete briefConfig.turn_target_override;
  delete briefConfig.cast_demand_override;
  const exportConfig = stageConfigs.export ?? {};
  const title = project?.title?.trim() || globalInputDefault(workflow, 'title') || workflow.name;
  const theme = Array.isArray(briefConfig.keywords)
    ? briefConfig.keywords.map(String).filter(Boolean).join('、')
    : String(briefConfig.core_concept ?? '');
  return {
    title,
    theme,
    project_id: project?.id ?? '',
    quality_mode: workflow.quality_mode,
    length_envelope: lengthEnvelope,
    scale_overrides: scaleOverrides,
    run_intent: {
      project_brief: {
        title,
        theme,
        genre: briefConfig.genre,
        audience: briefConfig.audience,
        narrative_profile: briefConfig.narrative_profile,
        core_concept: briefConfig.core_concept,
        keywords: briefConfig.keywords,
        taboos: briefConfig.taboos,
      },
      knowledge_strategy: {
        reference_mode: briefConfig.reference_mode,
        reference_keywords: briefConfig.reference_keywords,
        reference_query_intent: briefConfig.reference_query_intent,
        reference_urls: briefConfig.reference_urls,
        knowledge_base_doc_ids: briefConfig.knowledge_base_doc_ids,
        enable_web_search: briefConfig.enable_web_search,
        reference_summary: briefConfig.reference_summary,
      },
    },
    export_preferences: {
      format: String(exportConfig.export_format) as 'md' | 'json' | 'zip',
      author: String(exportConfig.author ?? ''),
      version_note: String(exportConfig.version_note ?? ''),
    },
  };
}
