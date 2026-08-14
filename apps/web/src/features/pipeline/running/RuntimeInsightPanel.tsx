import { BarChart3, DatabaseZap, FileText, Globe2, Network } from 'lucide-react';
import type { CharacterGraph, KnowledgeDocument, RunEvent, WorkflowDefinition } from '../contracts';
import type { WorldbuildingView } from '../lib/stageConfig';
import { chapterCapacitySummary, latestChapterCapacity } from '../lib/qualityGateProjection';
import { WorldbuildingPanel } from '../planning/insights/WorldbuildingPanel';
import { ChapterReviewPanel } from './insights/ChapterReviewPanel';
import { CharacterForceGraphPanel } from './insights/CharacterForceGraphPanel';
import { RuntimeKnowledgePanel } from './insights/RuntimeKnowledgePanel';
import type { RuntimePanelKey } from './stageRuntimeLayout';
import type { RuntimeStageProjection, RuntimeWritebackStatus } from './runtimeArtifactProjection';
import { parseCoverArtifact, parseExportArtifact } from './artifactsVnext';
import { ChapterContextManifestPanel } from './ChapterContextManifestPanel';
import type { ChapterContextManifestState } from '../state/useChapterContextManifest';

export type BriefArtifactDisplayStatus = 'draft' | 'confirmed';

export type RuntimeInsightContext = {
  events: RunEvent[];
  knowledgeDocuments: KnowledgeDocument[];
  memoryEvents: RunEvent[];
  briefArtifactStatus?: BriefArtifactDisplayStatus;
  workflow: WorkflowDefinition;
  characterGraphOverride?: CharacterGraph;
  briefWorldbuilding?: WorldbuildingView;
  artifactProjection: RuntimeStageProjection;
  writebackStatus: RuntimeWritebackStatus;
  onOpenKnowledgeManager: () => void;
  contextManifest: ChapterContextManifestState;
};

type RuntimeInsightPanelProps = RuntimeInsightContext & {
  panel: RuntimePanelKey;
  detail?: boolean;
  onEditBrief?: (target: 'worldbuilding' | 'character') => void;
};

export function RuntimeInsightPanel({
  events,
  knowledgeDocuments,
  memoryEvents,
  panel,
  detail = false,
  briefArtifactStatus,
  workflow,
  characterGraphOverride,
  briefWorldbuilding,
  artifactProjection,
  writebackStatus,
  onEditBrief,
  onOpenKnowledgeManager,
  contextManifest,
}: RuntimeInsightPanelProps) {
  if (panel === 'contextManifest') {
    return <ChapterContextManifestPanel {...contextManifest} detail={detail} />;
  }
  if (panel === 'character') {
    return (
      <CharacterForceGraphPanel
        events={events}
        graphOverride={characterGraphOverride}
        onEdit={onEditBrief ? () => onEditBrief('character') : undefined}
        qualityMode={workflow.quality_mode}
        stageEnrichment={artifactProjection.character
          ? { label: '当前 Artifact 人物引用', detail: artifactProjection.character }
          : undefined}
        artifactStatus={briefArtifactStatus}
      />
    );
  }
  if (panel === 'worldbuilding') {
    return (
      <WorldbuildingPanel
        events={events}
        onEdit={onEditBrief ? () => onEditBrief('worldbuilding') : undefined}
        stageEnrichment={artifactProjection.worldbuilding
          ? { label: '当前 Artifact 世界规则引用', detail: artifactProjection.worldbuilding }
          : undefined}
        artifactStatus={briefArtifactStatus}
        worldbuilding={briefWorldbuilding}
      />
    );
  }
  if (panel === 'knowledge') {
    return <RuntimeKnowledgePanel documents={knowledgeDocuments} events={events} onOpenKnowledge={onOpenKnowledgeManager} />;
  }
  if (panel === 'wiki') {
    const writebacks = [...events, ...memoryEvents].filter((event) => event.type.startsWith('writeback.'));
    return <EventStatusPanel
      title="Wiki 与 Canon 写回"
      description={artifactProjection.foreshadow || `${writebackStatus.label}${writebackStatus.transactionId ? ` · ${writebackStatus.transactionId}` : ''}`}
      events={writebacks}
    />;
  }
  if (panel === 'coverQuality') {
    const completed = events.find((event) => event.type === 'artifact.committed' && event.stage_id === 'cover');
    const result = completed?.payload ? JSON.stringify(completed.payload) : '';
    const artifact = parseCoverArtifact(result).artifact;
    return <StageSummaryPanel
      title="封面交付摘要"
      description={artifact?.brief.concept || '等待封面 Artifact'}
      metrics={[artifact?.selected_asset_id ? '已选择正式资产' : '尚未选择正式资产']}
    />;
  }
  if (panel === 'exportSummary') {
    const completed = events.find((event) => event.type === 'artifact.committed' && event.stage_id === 'export');
    const result = completed?.payload ? JSON.stringify(completed.payload) : '';
    const artifact = parseExportArtifact(result).artifact;
    return <StageSummaryPanel
      title="导出摘要"
      description={artifact ? `${artifact.format.toUpperCase()} 交付包` : '等待导出 Artifact'}
      metrics={artifact ? [`${artifact.chapter_version_ids.length} 个章节版本`, artifact.cover_asset_id ? '包含封面资产' : '无封面资产'] : ['尚未生成清单']}
    />;
  }
  const capacity = latestChapterCapacity(events);
  return <ChapterReviewPanel
    chapterId={contextManifest.record?.chapter_id ?? ''}
    events={events}
    summary={capacity ? chapterCapacitySummary(capacity) : undefined}
  />;
}

export function RuntimeCompactTile({
  events,
  memoryEvents,
  panel,
  characterGraphOverride,
  artifactProjection,
  writebackStatus,
  workflow,
  onOpen,
  contextManifest,
}: Pick<RuntimeInsightContext, 'events' | 'memoryEvents' | 'characterGraphOverride' | 'artifactProjection' | 'writebackStatus' | 'workflow' | 'contextManifest'> & {
  panel: RuntimePanelKey;
  onOpen: () => void;
  contextManifest: ChapterContextManifestState;
}) {
  const qualityCount = events.filter((event) => event.type === 'review.completed' || event.type === 'review.unavailable').length;
  const wikiCount = [...events, ...memoryEvents].filter((event) => event.type === 'evidence.proposed' || event.type === 'writeback.committed').length;
  const graph = characterGraphOverride;
  const characterMetric = graph
    ? `已冻结 ${graph.nodes.length} 人 · ${graph.edges.length} 关系`
    : '暂无已冻结关系';
  const worldbuildingMetric = artifactProjection.worldbuilding
    ? '当前阶段引用世界规则'
      : '打开设定摘要';
  const config = {
    character: { icon: Network, title: '人物关系', metric: artifactProjection.character ? '当前阶段引用冻结人物' : characterMetric },
    worldbuilding: { icon: Globe2, title: '世界观', metric: worldbuildingMetric },
    quality: { icon: BarChart3, title: '质量检查', metric: qualityCount ? `${qualityCount} 项检查` : '暂无检查' },
    wiki: { icon: DatabaseZap, title: 'Wiki 事实层', metric: writebackStatus.status === 'not_proposed' ? `${wikiCount} 事件` : writebackStatus.label },
    knowledge: { icon: DatabaseZap, title: '知识库', metric: '参考入口' },
    contextManifest: { icon: FileText, title: '本章上下文', metric: contextManifest.record ? `${contextManifest.record.manifest.snippets.length} 个片段` : contextManifest.status === 'loading' ? '读取中' : '不可用' },
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

function EventStatusPanel({ title, description, events }: { title: string; description: string; events: RunEvent[] }) {
  return (
    <section className="config-section runtime-insight-card stage-status-insight">
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="chip-grid">
        {events.slice(0, 6).map((event) => (
          <span key={event.event_id}>{event.chapter_id || event.stage_id || 'run'} · {event.type}</span>
        ))}
        {!events.length ? <span>暂无运行事件</span> : null}
      </div>
    </section>
  );
}

function StageSummaryPanel({ title, description, metrics }: { title: string; description: string; metrics: string[] }) {
  return (
    <section className="config-section runtime-insight-card stage-status-insight">
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="chip-grid">
        {metrics.map((metric) => <span key={metric}>{metric}</span>)}
      </div>
    </section>
  );
}
