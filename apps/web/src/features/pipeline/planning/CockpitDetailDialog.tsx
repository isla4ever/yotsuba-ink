import { Activity, BarChart3, DatabaseZap, FileText, Globe2, ShieldCheck, X } from 'lucide-react';
import { motion } from 'motion/react';
import type { KnowledgeDocument, QualityEvent, RunEvent, WorkflowStage } from '../contracts';
import { extractWorldbuilding } from '../lib/stageConfig';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { stageLabelForUi } from '../lib/display';
import { runEventLabel } from '../lib/runEventLabels';
import { stageArtifactLabel } from '../lib/planningReadiness';
import { displayRunLogEvents, latestNodeStatus } from './cockpitRuntime';

type DetailPanel = 'knowledge' | 'worldbuilding' | 'wiki' | 'quality' | 'stage';

type Props = {
  kind: DetailPanel;
  documents?: KnowledgeDocument[];
  events: RunEvent[];
  onClose: () => void;
  stage?: WorkflowStage;
};

export function CockpitDetailDialog({ documents = [], events, kind, onClose, stage }: Props) {
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  return (
      <motion.div animate="animate" className="cockpit-detail-backdrop app-overlay-backdrop" exit="exit" initial="initial" role="presentation" onClick={onClose} variants={backdropMotionVariants}>
        <motion.section
          animate="animate"
          aria-label={kind === 'stage' && stage ? `${stageLabelForUi(stage)}只读阶段快照` : '运行观察详情'}
          aria-modal="true"
          className="cockpit-detail-dialog app-dialog-surface"
          exit="exit"
          initial="initial"
          role="dialog"
          ref={dialogRef}
          tabIndex={-1}
          onClick={(event) => event.stopPropagation()}
          variants={dialogMotionVariants}
        >
        <button aria-label="关闭详情" className="cockpit-detail-close" onClick={onClose} type="button">
          <X size={22} />
        </button>
        {kind === 'knowledge' ? <KnowledgeDetail documents={documents} events={events} /> : null}
        {kind === 'worldbuilding' ? <WorldbuildingDetail events={events} /> : null}
        {kind === 'wiki' ? <WikiDetail events={events} /> : null}
        {kind === 'quality' ? <QualityDetail events={events} /> : null}
        {kind === 'stage' && stage ? <StageDetail events={events} stage={stage} /> : null}
        </motion.section>
      </motion.div>
  );
}

function StageDetail({ events, stage }: { events: RunEvent[]; stage: WorkflowStage }) {
  const runtime = latestNodeStatus(events, stage.id);
  const items = displayRunLogEvents(events, stage);
  const stageEventCount = events.filter((event) => event.node_id === stage.id).length;
  return (
    <>
      <p className="eyebrow">只读阶段快照</p>
      <h2><FileText size={20} />{stageLabelForUi(stage)}</h2>
      <div className="cockpit-detail-stats">
        <span><strong>{runtimeStatusLabel(runtime.status)}</strong>状态</span>
        <span><strong>{stageEventCount}</strong>事件</span>
        <span><strong>{runtime.completedSeconds ? `${runtime.completedSeconds}s` : '--'}</strong>耗时</span>
      </div>
      <p className="cockpit-detail-lede">阶段产物：{stageArtifactLabel(stage)}</p>
      <div className="cockpit-detail-list">
        {items.map((item) => (
          <article key={item.key}>
            <strong><Activity size={14} />{item.title}</strong>
            <span>{item.detail}</span>
            <small>{item.status === 'done' ? '已完成' : item.status === 'running' ? '进行中' : '等待中'}</small>
          </article>
        ))}
        {!items.length ? <CockpitDetailEmpty title="等待阶段事件" detail="本阶段尚未收到可展示的运行产物或状态事件。" /> : null}
      </div>
    </>
  );
}

function runtimeStatusLabel(status: string) {
  if (status === 'running') return '执行中';
  if (status === 'done') return '已完成';
  if (status === 'failed') return '失败';
  return '等待中';
}

function KnowledgeDetail({ documents, events }: { documents: KnowledgeDocument[]; events: RunEvent[] }) {
  const ragEvents = events.filter((event) => event.type.startsWith('rag_') || event.type.startsWith('reference_'));
  const chunks = documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
  return (
    <>
      <p className="eyebrow">创作依据</p>
      <h2><DatabaseZap size={20} />知识库资料台</h2>
      <div className="cockpit-detail-stats">
        <span><strong>{documents.length}</strong>资料</span>
        <span><strong>{chunks}</strong>片段</span>
        <span><strong>{ragEvents.length}</strong>事件</span>
      </div>
      <div className="cockpit-detail-list">
        {documents.slice(0, 12).map((doc) => (
          <article key={doc.doc_id}>
            <strong><FileText size={14} />{doc.title || doc.filename}</strong>
            <span>{doc.status} · {doc.chunk_count} 片段</span>
            <small>{doc.filename}</small>
          </article>
        ))}
        {!documents.length ? <p className="cockpit-detail-empty app-empty-state">暂无项目资料。信息推荐会先使用默认题材输入与联网参考；上传资料后，这里会显示被命中的项目知识。</p> : null}
      </div>
    </>
  );
}

function WorldbuildingDetail({ events }: { events: RunEvent[] }) {
  const world = extractWorldbuilding(events);
  if (!world.seed) return <CockpitDetailEmpty title="世界观尚未生成" detail="小说信息推荐确认后，这里会展示世界规则、风格基调和后续影响。" />;
  return (
    <>
      <p className="eyebrow">设定资产</p>
      <h2><Globe2 size={20} />世界观详情</h2>
      <p className="cockpit-detail-lede">{world.seed}</p>
      <div className="cockpit-detail-grid">
        <DetailSection title="硬设定" items={world.rules} />
        <DetailSection title="风格基调" items={[world.tone]} />
        <DetailSection title="后续影响" items={world.impact} />
      </div>
    </>
  );
}

function WikiDetail({ events }: { events: RunEvent[] }) {
  const reads = events.filter((event) => event.type === 'memory_context_loaded');
  const writes = events.filter((event) => event.type === 'memory_writeback_completed');
  const records = [...reads, ...writes].slice(0, 14);
  return (
    <>
      <p className="eyebrow">事实记忆</p>
      <h2><DatabaseZap size={20} />Wiki 事实层</h2>
      <div className="cockpit-detail-stats">
        <span><strong>{reads.length}</strong>读取</span>
        <span><strong>{writes.length}</strong>写回</span>
      </div>
      <div className="cockpit-detail-list">
        {records.map((event, index) => (
          <article key={`${event.type}-${event.node_id}-${index}`}>
            <strong>{event.type === 'memory_context_loaded' ? '读取约束' : '写回记忆'}</strong>
            <span>{event.label ?? event.node_id ?? '运行阶段'}</span>
            <small>{runEventLabel(event.type)}</small>
          </article>
        ))}
        {!records.length ? <p className="muted">运行到细纲和正文阶段后，这里会出现实际读取和写回的 Wiki 记录。</p> : null}
      </div>
    </>
  );
}

function QualityDetail({ events }: { events: RunEvent[] }) {
  const qualityEvents = qualityEventsFor(events);
  const avg = qualityEvents.reduce((sum, event) => sum + event.score, 0) / Math.max(1, qualityEvents.length);
  const avgLabel = qualityEvents.length ? avg.toFixed(2) : '--';
  const blocked = qualityEvents.filter((event) => !event.passed).length;
  return (
    <>
      <p className="eyebrow">质量检查</p>
      <h2><ShieldCheck size={20} />质量检查详情</h2>
      <div className="cockpit-detail-stats">
        <span><strong>{avgLabel}</strong>均分</span>
        <span><strong>{blocked}</strong>风险</span>
        <span><strong>{qualityEvents.length}</strong>检查</span>
      </div>
      <div className="cockpit-quality-meter"><i style={{ width: `${Math.min(100, avg * 100)}%` }} /></div>
      <div className="cockpit-detail-list quality">
        {qualityEvents.map((event) => (
          <article className={event.passed ? 'passed' : 'blocked'} key={`${event.node_id}-${event.score}`}>
            <strong><BarChart3 size={14} />{event.label}</strong>
            <span>{event.score.toFixed(2)} / {event.min_score.toFixed(2)}</span>
            <small>{event.warnings[0] ?? (event.passed ? '本次检查通过' : '未返回具体问题')}</small>
          </article>
        ))}
        {!qualityEvents.length ? <CockpitDetailEmpty title="等待质量检查" detail="梗概阶段开始后，质量检查结果会出现在这里。" /> : null}
      </div>
    </>
  );
}

function DetailSection({ items, title }: { title: string; items: string[] }) {
  return (
    <article>
      <strong>{title}</strong>
      {items.map((item) => <span key={item}>{item}</span>)}
    </article>
  );
}

function CockpitDetailEmpty({ detail, title }: { detail: string; title: string }) {
  return (
    <div className="cockpit-detail-empty app-empty-state" role="status">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function qualityEventsFor(events: RunEvent[]) {
  const actual = events
    .filter((event) => event.type === 'quality_check_completed')
    .map((event) => event.quality)
    .filter(Boolean) as QualityEvent[];
  return actual;
}
