import { BarChart3, DatabaseZap, Globe2, Network } from 'lucide-react';
import type { ChapterQualityRepairTarget, CharacterGraph, KnowledgeDocument, RunEvent, WorkflowDefinition } from '../contracts';
import type { WorldbuildingView } from '../lib/stageConfig';
import { WorldbuildingPanel } from '../planning/insights/WorldbuildingPanel';
import { CharacterForceGraphPanel } from './insights/CharacterForceGraphPanel';
import { QualityMonitorPanel } from './insights/QualityMonitorPanel';
import { RuntimeKnowledgePanel } from './insights/RuntimeKnowledgePanel';
import { WikiMemoryPanel } from './insights/WikiMemoryPanel';
import type { RuntimePanelKey } from './stageRuntimeLayout';
import type { ChapterReviewInsight } from './writingArtifactModel';
import type { InfoEditorTarget } from './infoRecommendationModel';
import { coverStageSummary } from './coverPresentation';
import { exportStageSummary } from './exportSummaryModel';
import { coverArtifact, exportArtifact } from './stageArtifacts';

export type RuntimeWritebacks = Partial<Record<'character' | 'worldbuilding' | 'foreshadow', string>>;
export type InfoArtifactDisplayStatus = 'draft' | 'confirmed';

export type RuntimeInsightContext = {
  events: RunEvent[];
  knowledgeDocuments: KnowledgeDocument[];
  memoryEvents: RunEvent[];
  infoArtifactStatus?: InfoArtifactDisplayStatus;
  workflow: WorkflowDefinition;
  characterGraphOverride?: CharacterGraph;
  infoWorldbuilding?: WorldbuildingView;
  summaryWritebacks: RuntimeWritebacks;
  outlineWritebacks: RuntimeWritebacks;
  detailWritebacks: RuntimeWritebacks;
  chapterReview?: ChapterReviewInsight;
  onOpenKnowledgeManager: () => void;
  onRepairQualityFinding?: (target: ChapterQualityRepairTarget) => void;
};

type RuntimeInsightPanelProps = RuntimeInsightContext & {
  panel: RuntimePanelKey;
  onEditInfo?: (target: InfoEditorTarget) => void;
};

export function RuntimeInsightPanel({
  events,
  knowledgeDocuments,
  memoryEvents,
  panel,
  infoArtifactStatus,
  workflow,
  characterGraphOverride,
  infoWorldbuilding,
  outlineWritebacks,
  summaryWritebacks,
  detailWritebacks,
  chapterReview,
  onEditInfo,
  onOpenKnowledgeManager,
  onRepairQualityFinding,
}: RuntimeInsightPanelProps) {
  if (panel === 'character') {
    return (
      <CharacterForceGraphPanel
        events={events}
        graphOverride={characterGraphOverride}
        onEdit={onEditInfo ? () => onEditInfo('character') : undefined}
        qualityMode={workflow.quality_mode}
        stageEnrichment={detailWritebacks.character
          ? { label: '细纲人物变化预览', detail: detailWritebacks.character }
          : outlineWritebacks.character
            ? { label: '分卷人物承接预览', detail: outlineWritebacks.character }
            : summaryWritebacks.character
              ? { label: '梗概人物深化', detail: summaryWritebacks.character }
              : chapterReview?.proposal?.counts.character
                ? { label: `${chapterReview.chapter}人物提案`, detail: '待正文定稿后写入人物关系网' }
                : undefined}
        artifactStatus={infoArtifactStatus}
      />
    );
  }
  if (panel === 'worldbuilding') {
    return (
      <WorldbuildingPanel
        events={events}
        onEdit={onEditInfo ? () => onEditInfo('worldbuilding') : undefined}
        stageEnrichment={detailWritebacks.worldbuilding
          ? { label: '细纲事实写回预览', detail: detailWritebacks.worldbuilding }
          : outlineWritebacks.worldbuilding
            ? { label: '世界观揭示预览', detail: outlineWritebacks.worldbuilding }
            : undefined}
        artifactStatus={infoArtifactStatus}
        worldbuilding={infoWorldbuilding}
      />
    );
  }
  if (panel === 'knowledge') {
    return <RuntimeKnowledgePanel documents={knowledgeDocuments} events={events} onOpenKnowledge={onOpenKnowledgeManager} />;
  }
  if (panel === 'wiki') {
    return (
      <WikiMemoryPanel
        chapterReview={chapterReview}
        events={[...events, ...memoryEvents]}
        qualityMode={workflow.quality_mode}
        stageEnrichment={detailWritebacks.foreshadow ? { label: '细纲伏笔账本预览', detail: detailWritebacks.foreshadow } : undefined}
      />
    );
  }
  if (panel === 'coverQuality') {
    const completed = events.find((event) => event.type === 'node_completed' && event.node_id === 'cover');
    const result = completed?.result ? (typeof completed.result === 'string' ? completed.result : JSON.stringify(completed.result)) : '';
    const progress = events.find((event) => event.type === 'asset_progress_updated' && event.node_id === 'cover');
    const summary = coverStageSummary(coverArtifact(result), progress?.score);
    return <StageSummaryPanel title="封面交付摘要" description={summary.description} metrics={summary.metrics} />;
  }
  if (panel === 'exportSummary') {
    const completed = events.find((event) => event.type === 'node_completed' && event.node_id === 'export');
    const result = completed?.result ? (typeof completed.result === 'string' ? completed.result : JSON.stringify(completed.result)) : '';
    const summary = exportStageSummary(exportArtifact(result));
    return <StageSummaryPanel title="导出摘要" description={summary.description} metrics={summary.metrics} />;
  }
  return <QualityMonitorPanel chapterReview={chapterReview} events={events} stages={workflow.nodes} onRepairQualityFinding={onRepairQualityFinding} />;
}

export function RuntimeCompactTile({
  events,
  memoryEvents,
  panel,
  characterGraphOverride,
  detailWritebacks,
  outlineWritebacks,
  summaryWritebacks,
  workflow,
  onOpen,
}: Pick<RuntimeInsightContext, 'events' | 'memoryEvents' | 'characterGraphOverride' | 'detailWritebacks' | 'outlineWritebacks' | 'summaryWritebacks' | 'workflow'> & {
  panel: RuntimePanelKey;
  onOpen: () => void;
}) {
  const qualityCount = events.filter((event) => event.type === 'quality_check_completed').length;
  const wikiCount = [...events, ...memoryEvents].filter((event) => event.type === 'memory_context_loaded' || event.type === 'memory_writeback_completed').length;
  const eventGraph = events.find((event) => event.type === 'character_graph_updated' && event.character_graph)?.character_graph;
  const graph = characterGraphOverride ?? eventGraph;
  const characterMetric = graph
    ? `${graph.nodes.length} 人 · ${graph.edges.length} 关系`
    : '暂无关系数据';
  const worldbuildingMetric = detailWritebacks.worldbuilding
    ? '细纲事实待定稿'
    : outlineWritebacks.worldbuilding
      ? '分卷揭示待定稿'
      : '打开设定摘要';
  const config = {
    character: { icon: Network, title: '人物关系', metric: summaryWritebacks.character || outlineWritebacks.character || detailWritebacks.character ? '有阶段变化待定稿' : characterMetric },
    worldbuilding: { icon: Globe2, title: '世界观', metric: worldbuildingMetric },
    quality: { icon: BarChart3, title: '质量检查', metric: qualityCount ? `${qualityCount} 项检查` : '暂无检查' },
    wiki: { icon: DatabaseZap, title: 'Wiki 事实层', metric: `${wikiCount} 事件` },
    knowledge: { icon: DatabaseZap, title: '知识库', metric: '参考入口' },
    coverQuality: { icon: BarChart3, title: '封面质量', metric: '已合并主区' },
    exportSummary: { icon: DatabaseZap, title: '导出摘要', metric: '已合并主区' },
  }[panel];
  const Icon = config.icon;
  return (
    <button aria-label={`打开${config.title}详情`} className={`runtime-compact-tile ${panel}`} onClick={onOpen} type="button">
      <Icon size={15} />
      <span>
        <strong>{config.title}</strong>
        <small>{config.metric}</small>
      </span>
    </button>
  );
}

function StageSummaryPanel({ title, description, metrics }: { title: string; description: string; metrics: string[] }) {
  return (
    <section className="config-section runtime-insight-card stage-summary-insight">
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="chip-grid">
        {metrics.map((metric) => <span key={metric}>{metric}</span>)}
      </div>
    </section>
  );
}
