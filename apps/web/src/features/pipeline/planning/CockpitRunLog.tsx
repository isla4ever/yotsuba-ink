import { Activity, CheckCircle2, ChevronDown, Clock3, FileText, Gauge, RadioTower, ShieldCheck, Terminal } from 'lucide-react';
import { useState, type CSSProperties } from 'react';
import type { RunEvent, WorkflowStage } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { stageLabelForUi } from '../lib/display';
import { settlementNextStageLabel, stageSettlementSummary } from '../lib/stageSettlement';
import { compactStreamPreview, splitStreamBlocks } from '../lib/streamText';
import { useStreamReveal } from '../state/useStreamReveal';
import { displayRunLogEvents, latestNodeStatus, type DisplayRunLogItem } from './cockpitRuntime';

type Props = {
  activeStage: WorkflowStage;
  elapsed: number;
  events: RunEvent[];
  hasTimer: boolean;
  detailAvailable: boolean;
  onOpenStage: () => void;
};

export function CockpitRunLog({ activeStage, detailAvailable, elapsed, events, hasTimer, onOpenStage }: Props) {
  const displayEvents = displayRunLogEvents(events, activeStage);
  const status = latestNodeStatus(events, activeStage.id).status;
  return (
    <section className="cockpit-run-log">
      <div className="cockpit-run-log-head">
        <div>
          <p className="eyebrow">运行记录</p>
          <h3><Activity size={15} />运行日志</h3>
        </div>
        <button
          aria-label={detailAvailable ? '打开当前阶段详情' : '阶段详情启动后可用'}
          disabled={!detailAvailable}
          onClick={onOpenStage}
          title={detailAvailable ? '打开当前阶段详情' : '启动创作后可查看阶段详情'}
          type="button"
        >
          <FileText size={14} />
          <span>{detailAvailable ? '详情' : '启动后可用'}</span>
        </button>
      </div>
      <div className="cockpit-run-current">
        <div>
          <span className={`run-status-dot ${status}`} />
          <strong>{stageLabelForUi(activeStage)}</strong>
          <small>{statusLabel(status)}</small>
        </div>
        <span><Clock3 size={13} />{hasTimer ? `${elapsed}s` : '等待'}</span>
      </div>
      <div className="cockpit-run-stream">
        {displayEvents.length ? displayEvents.map((event, index) => (
          <article className={`tone-${event.tone ?? 'support'} lane-${event.agent ?? 'support'} state-${event.status ?? 'idle'}`} key={event.key} style={{ '--log-index': index } as CSSProperties}>
            <span className="log-event-glyph">{iconForTone(event)}</span>
            <small>{event.title}</small>
            {event.agent === 'main' ? (
              <div className={`log-main-copy ${event.status === 'running' ? 'streaming' : ''}`}>
                {typeof event.progress === 'number' ? <ProgressRail active={event.status === 'running'} value={event.progress} /> : null}
                <SmoothLogText active={event.status === 'running'} value={event.detail} />
              </div>
            ) : (
              <>
                <p>{event.detail}</p>
                {typeof event.progress === 'number' ? <ProgressRail active={event.status === 'running'} value={event.progress} compact /> : null}
              </>
            )}
          </article>
        )) : (
          <div className="cockpit-run-empty">
            <Gauge size={18} />
            <strong>等待创作启动</strong>
            <span>启动创作后，各阶段的进展会实时显示在这里。</span>
          </div>
        )}
      </div>
      <CockpitSettlementCard events={events} />
    </section>
  );
}

/**
 * The settlement card only shows facts emitted by the Graph envelope.
 */
function CockpitSettlementCard({ events }: { events: RunEvent[] }) {
  const settled = events.find((event) => (
    event.stage_id
    && event.stage_id !== 'info'
    && (event.type === 'checkpoint.saved' || event.type === 'artifact.committed')
  ));
  const [expandedKey, setExpandedKey] = useState('');
  if (!settled?.stage_id) return null;
  const stageId = settled.stage_id;
  const label = settlementNextStageLabel(stageId);
  const expanded = expandedKey === stageId;
  const summary = stageSettlementSummary(events, { id: stageId });
  return (
    <div className="cockpit-settlement-card">
      <button
        aria-expanded={expanded}
        onClick={() => setExpandedKey(expanded ? '' : stageId)}
        title={expanded ? '收起阶段结算摘要' : '展开阶段结算摘要'}
        type="button"
      >
        <RadioTower size={13} />
        <strong>{label} · 阶段结算</strong>
        <ChevronDown className={expanded ? 'open' : ''} size={13} />
      </button>
      {expanded ? (
        <dl>
          <div><dt>检查点</dt><dd>{summary.checkpointId || '等待保存'}</dd></div>
          <div><dt>Artifact</dt><dd>{summary.committedArtifact ? '已提交' : '等待提交'}</dd></div>
          <div><dt>审稿</dt><dd>{summary.reviewCount} 完成 · {summary.unavailableReviewCount} 不可用</dd></div>
          <div><dt>写回</dt><dd>{writebackLabel(summary.writebackStatus)}</dd></div>
        </dl>
      ) : null}
    </div>
  );
}

function writebackLabel(status: ReturnType<typeof stageSettlementSummary>['writebackStatus']) {
  return {
    none: '未触发',
    queued: '已排队',
    committed: '已提交',
    failed: '失败',
  }[status];
}

function SmoothLogText({ active, value }: { active: boolean; value: string }) {
  const preview = compactStreamPreview(value, 3);
  const { text: visible } = useStreamReveal(preview, { active, mode: 'line', tickMs: 44 });
  const lines = splitStreamBlocks(visible);
  return (
    <div className="smooth-stream-text log-stream-text">
      {lines.map((line, lineIndex) => (
        <p className="smooth-stream-line" key={`${lineIndex}-${line.slice(0, 18)}`}>
          <span className="log-line-prefix">{active && lineIndex === lines.length - 1 ? '>' : '·'}</span>
          <span className="log-line-text">
            {line}
            {active && lineIndex === lines.length - 1 ? <span className="agent-stream-cursor" /> : null}
          </span>
        </p>
      ))}
    </div>
  );
}

function ProgressRail({ active, compact = false, value }: { active: boolean; compact?: boolean; value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div
      aria-label={`进度 ${pct}%`}
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={pct}
      className={`log-progress-rail${compact ? ' compact' : ''}${active ? ' running' : ''}`}
      role="progressbar"
      style={{ '--progress-pct': `${pct}%` } as CSSProperties}
    >
      <i />
      <span>{pct}%</span>
    </div>
  );
}

function iconForTone(event: DisplayRunLogItem) {
  if (event.agent === 'settlement') return <RadioTower size={13} />;
  if (event.agent === 'provider') return <ButtonLoadingIndicator />;
  if (event.status === 'done') return <CheckCircle2 size={13} />;
  if (event.status === 'running') return <ButtonLoadingIndicator />;
  if (event.agent === 'wiki' || event.agent === 'quality') return <ShieldCheck size={13} />;
  if (event.tone === 'milestone') return <RadioTower size={13} />;
  if (event.tone === 'content') return <Terminal size={13} />;
  return <Activity size={13} />;
}

function statusLabel(status: string) {
  if (status === 'running') return '执行中';
  if (status === 'done') return '已完成';
  if (status === 'failed') return '失败';
  return '等待中';
}
