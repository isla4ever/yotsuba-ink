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
  const brief = workflow.nodes.find((stage) => stage.id === 'brief');
  const briefDefaults = fieldDefaults(brief);
  const hasModelConfig = providerReadiness.status === 'ready' && Boolean(providerReadiness.report?.ok);
  const briefKeys = [
    'genre',
    'narrative_profile',
    'audience',
    'core_concept',
    'keywords',
    'taboos',
  ];
  const hasBrief = briefKeys.every((key) => hasValue(briefDefaults[key]));
  const referenceMode = String(briefDefaults.reference_mode || 'smart_search');
  const hasReference = referenceMode === 'smart_search'
    ? Boolean(briefDefaults.enable_web_search) || hasValue(briefDefaults.reference_keywords) || hasValue(briefDefaults.reference_query_intent)
    : referenceMode === 'url'
      ? hasValue(briefDefaults.reference_urls)
      : hasValue(briefDefaults.reference_query_intent) || hasValue(briefDefaults.knowledge_base_doc_ids);
  const needsKnowledge = referenceMode === 'knowledge_base' || (referenceMode === 'smart_search' && briefDefaults.enable_web_search === false);
  const hasKnowledge = !needsKnowledge || knowledgeDocuments.length > 0 || hasValue(briefDefaults.knowledge_base_doc_ids);
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
