import { Activity, BarChart3, DatabaseZap, FileText, Globe2, ShieldCheck, X } from 'lucide-react';
import { motion } from 'motion/react';
import type { KnowledgeDocument, RunEvent, WorkflowStage } from '../contracts';
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
        {!documents.length ? <p className="cockpit-detail-empty app-empty-state">暂无项目资料。只有上传并选中的知识库文档会在前置规划中参与检索。</p> : null}
      </div>
    </>
  );
}

function WorldbuildingDetail({ events }: { events: RunEvent[] }) {
  const world = extractWorldbuilding(events);
  if (!world.seed) return <CockpitDetailEmpty title="世界观尚未生成" detail="创作立项确认后，这里会展示世界规则、风格基调和后续影响。" />;
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
  const reads = events.filter((event) => event.type === 'evidence.proposed');
  const writes = events.filter((event) => event.type === 'writeback.committed');
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
            <strong>{event.type === 'evidence.proposed' ? '证据提案' : '正式写回'}</strong>
            <span>{event.chapter_id || event.stage_id || event.node_id || '运行阶段'}</span>
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
  const blocked = qualityEvents.filter((event) => event.type === 'review.unavailable').length;
  const findings = qualityEvents.reduce((total, event) => total + (Array.isArray(event.payload?.findings) ? event.payload.findings.length : 0), 0);
  return (
    <>
      <p className="eyebrow">质量检查</p>
      <h2><ShieldCheck size={20} />质量检查详情</h2>
      <div className="cockpit-detail-stats">
        <span><strong>{findings}</strong>发现</span>
        <span><strong>{blocked}</strong>风险</span>
        <span><strong>{qualityEvents.length}</strong>检查</span>
      </div>
      <div className="cockpit-detail-list quality">
        {qualityEvents.map((event) => (
          <article className={event.type === 'review.unavailable' ? 'blocked' : 'passed'} key={event.event_id}>
            <strong><BarChart3 size={14} />{payloadText(event, 'role') || '审稿角色'}</strong>
            <span>{event.type === 'review.unavailable' ? '不可用' : '审稿完成'}</span>
            <small>{Array.isArray(event.payload?.findings) ? `${event.payload.findings.length} 个结构化发现` : '未返回发现'}</small>
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
  return events.filter((event) => event.type === 'review.completed' || event.type === 'review.unavailable');
}

function payloadText(event: RunEvent, key: string) {
  const value = event.payload?.[key];
  return typeof value === 'string' ? value : '';
}
