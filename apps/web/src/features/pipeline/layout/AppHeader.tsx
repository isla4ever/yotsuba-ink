import { CheckCircle2, Gauge, Layers3, LoaderCircle, Moon, Settings, Sun, TriangleAlert, Zap, type LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { CreationActionDock } from './CreationActionDock';
import { StageProgressNavigator } from './StageProgressNavigator';
import type { ConfigProgress, KnowledgeDocument, QualityMode, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';

type Props = {
  selectedStage: WorkflowStage;
  events: RunEvent[];
  workflow: WorkflowDefinition;
  knowledgeDocuments: KnowledgeDocument[];
  running: boolean;
  paused: boolean;
  theme: 'dark' | 'light';
  saveStatus: 'idle' | 'saving' | 'saved' | 'failed';
  qualityMode: QualityMode;
  onOpenSettings: () => void;
  onQualityModeChange: (mode: QualityMode) => void;
  onPause: () => void;
  onRun: () => void;
  onToggleTheme: () => void;
};

export function AppHeader({
  selectedStage,
  events,
  workflow,
  knowledgeDocuments,
  running,
  paused,
  theme,
  saveStatus,
  qualityMode,
  onOpenSettings,
  onQualityModeChange,
  onPause,
  onRun,
  onToggleTheme,
}: Props) {
  const [modeNotice, setModeNotice] = useState<QualityMode | null>(null);
  const configProgress = useMemo(() => buildConfigProgress(workflow, knowledgeDocuments), [workflow, knowledgeDocuments]);

  useEffect(() => {
    if (!modeNotice) return;
    const timer = window.setTimeout(() => setModeNotice(null), 1450);
    return () => window.clearTimeout(timer);
  }, [modeNotice]);

  const handleQualityModeChange = (mode: QualityMode) => {
    if (mode === qualityMode || (running && !paused)) return;
    onQualityModeChange(mode);
    setModeNotice(mode);
  };

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-mark">NW</div>
        <div>
          <p>Novel Workflow</p>
          <strong>小说流水线平台</strong>
        </div>
      </div>

      <div className="header-progress-slot">
        <StageProgressNavigator configProgress={configProgress} stage={selectedStage} events={events} />
      </div>

      <div className="header-actions">
        <span className={`save-state ${saveStatus}`}>
          <SaveStatusIcon status={saveStatus} />
        </span>
        <button className="icon-button tech-icon-button" onClick={onToggleTheme} title={theme === 'dark' ? '切换日间模式' : '切换夜间模式'}>
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button className="icon-button tech-icon-button" onClick={onOpenSettings} title="设置"><Settings size={16} /></button>
        <CreationActionDock
          disabled={running && !paused}
          paused={paused}
          qualityMode={qualityMode}
          running={running}
          onPause={onPause}
          onQualityModeChange={handleQualityModeChange}
          onRun={onRun}
        />
      </div>
      {modeNotice ? createPortal(<QualityModeNotice mode={modeNotice} onClose={() => setModeNotice(null)} />, document.body) : null}
    </header>
  );
}

function SaveStatusIcon({ status }: { status: Props['saveStatus'] }) {
  if (status === 'saving') return <LoaderCircle className="save-spin-icon" size={14} />;
  if (status === 'failed') return <TriangleAlert size={14} />;
  return <CheckCircle2 size={14} />;
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

function buildConfigProgress(workflow: WorkflowDefinition, knowledgeDocuments: KnowledgeDocument[]): ConfigProgress {
  const info = workflow.nodes.find((stage) => stage.id === 'info');
  const infoDefaults = fieldDefaults(info);
  const hasModelConfig = workflow.provider_profiles.some((provider) => provider.enabled && (provider.kind === 'mock' || provider.kind === 'image-mock' || Boolean(provider.base_url.trim() && provider.api_key_env.trim())));
  const briefKeys = ['genre', 'target_length', 'target_words_range', 'audience', 'core_concept', 'keywords', 'taboos'];
  const hasBrief = briefKeys.every((key) => hasValue(infoDefaults[key]));
  const referenceMode = String(infoDefaults.reference_mode || 'smart_search');
  const hasReference = referenceMode === 'smart_search'
    ? Boolean(infoDefaults.enable_web_search) || hasValue(infoDefaults.reference_keywords) || hasValue(infoDefaults.reference_query_intent)
    : referenceMode === 'url'
      ? hasValue(infoDefaults.reference_urls)
      : hasValue(infoDefaults.reference_query_intent) || hasValue(infoDefaults.knowledge_base_doc_ids);
  const needsKnowledge = referenceMode === 'knowledge_base' || (referenceMode === 'smart_search' && infoDefaults.enable_web_search === false);
  const hasKnowledge = !needsKnowledge || knowledgeDocuments.length > 0 || hasValue(infoDefaults.knowledge_base_doc_ids);
  const hasQuality = Boolean(workflow.quality_mode) && workflow.nodes.every((stage) => Number.isFinite(stage.quality_policy.min_score) && stage.quality_policy.min_score >= 0 && stage.quality_policy.min_score <= 1);
  const items = [
    { key: 'model', label: '模型/API', done: hasModelConfig },
    { key: 'brief', label: '小说 Brief', done: hasBrief },
    { key: 'reference', label: '参考源', done: hasReference },
    { key: 'knowledge', label: '知识库', done: hasKnowledge },
    { key: 'quality', label: '质量策略', done: hasQuality },
  ];
  return { completed: items.filter((item) => item.done).length, items };
}

function QualityModeNotice({ mode, onClose }: { mode: QualityMode; onClose: () => void }) {
  const copy = qualityModeCopy[mode];
  const Icon = copy.icon;
  return (
    <div className={`quality-mode-notice mode-${mode}`} role="presentation" onClick={onClose}>
      <section className="quality-mode-notice-card" onClick={(event) => event.stopPropagation()}>
        <span className="quality-mode-notice-orb"><Icon size={18} /></span>
        <div>
          <p className="eyebrow">Quality Mode</p>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <div className="quality-mode-notice-pills">
          <span><b>Token</b>{copy.cost}</span>
          <span><b>适用</b>{copy.useCase}</span>
        </div>
      </section>
    </div>
  );
}

const qualityModeCopy = {
  fast: {
    title: '极速预览',
    description: '单版本快速跑通主链路，优先验证题材方向与流程结构。',
    capability: '单版本生成，质量检查仅提示。',
    cost: '低消耗',
    useCase: '早期试想法',
    icon: Zap,
  },
  balanced: {
    title: '平衡创作',
    description: '关键节点保留择优能力，在质量、成本和稳定性之间取平衡。',
    capability: '正文默认双版本择优。',
    cost: '中等消耗',
    useCase: '常规章节产出',
    icon: Gauge,
  },
  deep: {
    title: '深度精修',
    description: '启用多候选评审、质量重试和更完整记忆检索，面向正式产出。',
    capability: '多候选评审与重试增强。',
    cost: '高消耗',
    useCase: '正式稿精修',
    icon: Layers3,
  },
} satisfies Record<QualityMode, { title: string; description: string; capability: string; cost: string; useCase: string; icon: LucideIcon }>;
