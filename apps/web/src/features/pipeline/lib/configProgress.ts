import type {
  ConfigProgress,
  KnowledgeDocument,
  ProviderReadinessReport,
  WorkflowDefinition,
  WorkflowStage,
} from '../contracts';

export type ProviderReadinessSnapshot = {
  report?: ProviderReadinessReport;
  status: 'idle' | 'loading' | 'ready' | 'failed';
};

export function buildConfigProgress(
  workflow: WorkflowDefinition,
  knowledgeDocuments: KnowledgeDocument[],
  providerReadiness: ProviderReadinessSnapshot,
): ConfigProgress {
  const info = workflow.nodes.find((stage) => stage.id === 'info');
  const infoDefaults = fieldDefaults(info);
  const hasModelConfig = providerReadiness.status === 'ready' && Boolean(providerReadiness.report?.ok);
  const briefKeys = ['genre', 'book_scale_target_mode', 'book_scale_target_value', 'audience', 'core_concept', 'keywords', 'taboos'];
  const hasBrief = briefKeys.every((key) => hasValue(infoDefaults[key]));
  const referenceMode = String(infoDefaults.reference_mode || 'smart_search');
  const hasReference = referenceMode === 'smart_search'
    ? Boolean(infoDefaults.enable_web_search) || hasValue(infoDefaults.reference_keywords) || hasValue(infoDefaults.reference_query_intent)
    : referenceMode === 'url'
      ? hasValue(infoDefaults.reference_urls)
      : hasValue(infoDefaults.reference_query_intent) || hasValue(infoDefaults.knowledge_base_doc_ids);
  const needsKnowledge = referenceMode === 'knowledge_base' || (referenceMode === 'smart_search' && infoDefaults.enable_web_search === false);
  const hasKnowledge = !needsKnowledge || knowledgeDocuments.length > 0 || hasValue(infoDefaults.knowledge_base_doc_ids);
  const hasQuality = ['fast', 'balanced', 'deep'].includes(workflow.quality_mode);
  const items = [
    { key: 'model', label: '模型/API', done: hasModelConfig },
    { key: 'brief', label: '小说 Brief', done: hasBrief },
    { key: 'reference', label: '参考源', done: hasReference },
    { key: 'knowledge', label: '知识库', done: hasKnowledge },
    { key: 'quality', label: '质量策略', done: hasQuality },
  ];
  return { completed: items.filter((item) => item.done).length, items };
}

function hasValue(value: unknown) {
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return Number.isFinite(value);
  return String(value ?? '').trim().length > 0;
}

function fieldDefaults(stage?: WorkflowStage) {
  return Object.fromEntries(stage?.input_schema.map((field) => [field.key, field.default ?? '']) ?? []);
}
