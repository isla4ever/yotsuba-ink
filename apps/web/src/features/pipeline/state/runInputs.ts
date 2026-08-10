import type { ProjectRecord, RunStartInputs, WorkflowDefinition } from '../contracts';
import type { RunSource } from '../lib/runSource';
import { stageInputDefaults } from '../lib/workflow';

type RunProjectContext = Pick<ProjectRecord, 'id' | 'title'> | null;

function globalInputDefault(workflow: WorkflowDefinition, key: string): string {
  const value = workflow.global_inputs.find((item) => item.key === key)?.default;
  return value == null ? '' : String(value);
}

/**
 * The title comes from the active project (falling back to
 * the workflow's own global_inputs default / name — never a hardcoded book
 * name), theme is derived from the Info-stage keywords, and project_id rides along
 * so the backend records explicit project ownership.
 */
export function buildRunInputs(
  workflow: WorkflowDefinition,
  runSource: RunSource = 'backend',
  project: RunProjectContext = null,
): RunStartInputs {
  const stageConfigs = Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stageInputDefaults(stage)]));
  const infoConfig = stageConfigs.info ?? {};
  const targetMode = infoConfig.book_scale_target_mode === 'total_chapters' ? 'total_chapters' : 'total_chars';
  const targetValue = Number(infoConfig.book_scale_target_value);
  delete infoConfig.book_scale_target_mode;
  delete infoConfig.book_scale_target_value;
  const exportConfig = stageConfigs.export ?? {};
  const title = project?.title?.trim() || globalInputDefault(workflow, 'title') || workflow.name;
  const theme = Array.isArray(infoConfig.keywords)
    ? infoConfig.keywords.map(String).filter(Boolean).join('、')
    : String(infoConfig.core_concept ?? '');
  return {
    title,
    theme,
    project_id: project?.id ?? '',
    quality_mode: workflow.quality_mode,
    book_scale_target: {
      target_mode: targetMode,
      target_value: targetValue,
    },
    run_intent: {
      project_brief: {
        title,
        theme,
        genre: infoConfig.genre,
        audience: infoConfig.audience,
        narrative_profile: infoConfig.narrative_profile,
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
    },
    export_preferences: {
      format: String(exportConfig.export_format) as 'md' | 'json' | 'zip',
      author: String(exportConfig.author ?? ''),
      version_note: String(exportConfig.version_note ?? ''),
    },
  };
}
