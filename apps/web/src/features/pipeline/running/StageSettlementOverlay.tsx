import { Activity, ArrowRight, Clock3, Coins, FileText, Gauge, ShieldCheck } from 'lucide-react';
import type { RunEvent, WorkflowStage } from '../contracts';
import {
  formatSettlementMs,
  settlementNextStageLabel,
  stageSettlementSummary,
} from '../lib/stageSettlement';
import { SETTLEMENT_DWELL_MS } from '../state/useRunTransitions';
import { LiquidGlassOverlay } from './LiquidGlassOverlay';

type Props = {
  events: RunEvent[];
  open: boolean;
  stage: WorkflowStage;
  /**
   * Phase 12 D7: dwellable settlement — the overlay stays until the user hits
   * 「继续」 or the 4s auto-continue elapses (static one-shot progress ring;
   * the global reduced-motion guard freezes the ring and the overlay shows
   * without transition via MotionConfig).
   */
  dwell?: boolean;
  onContinue?: () => void;
};

const RING_RADIUS = 8;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export function StageSettlementOverlay({ dwell = false, events, onContinue, open, stage }: Props) {
  // Phase 12 D1: real usage arrives as stage_usage_updated / stage_usage_finalized.
  const summary = stageSettlementSummary(events, stage);
  return (
    <LiquidGlassOverlay className="stage-settlement-overlay" open={open}>
      <div className="stage-settlement-card">
        <p className="eyebrow">阶段结算</p>
        <h2><Activity size={20} />{stage.label} 完成结算</h2>
        <div className="stage-settlement-metrics">
          <span><Clock3 size={13} />{summary.elapsedMs == null ? '暂无' : formatSettlementMs(summary.elapsedMs)}</span>
          <span><Gauge size={13} />{summary.tokens == null ? '暂无' : `用量 ${summary.tokens.toLocaleString()}`}</span>
          <span><Coins size={13} />{summary.costUsd == null ? '暂无' : `$${summary.costUsd.toFixed(3)}`}</span>
          <span><FileText size={13} />{summary.words ? `${summary.words.toLocaleString()} 字` : '产物已写入'}</span>
          {summary.qualityScore != null ? (
            <span><ShieldCheck size={13} />Q {summary.qualityScore.toFixed(2)}</span>
          ) : null}
        </div>
        <p>
          {summary.qualityScore != null
            ? `质量检查 Q ${summary.qualityScore.toFixed(2)} · ${summary.qualityFindings} 个发现`
            : summary.message || '产物已完成，正在准备进入下一阶段。'}
        </p>
        <small>{summary.nextStep ? `即将进入：${settlementNextStageLabel(summary.nextStep)}` : '正在完成阶段交接'}</small>
        {dwell && onContinue ? (
          <div className="stage-settlement-actions">
            <button autoFocus className="tech-button stage-settlement-continue" onClick={onContinue} type="button">
              <SettlementCountdownRing key={stage.id} />
              <span>继续</span>
            </button>
            <small>{Math.round(SETTLEMENT_DWELL_MS / 1000)} 秒后自动继续</small>
          </div>
        ) : null}
      </div>
    </LiquidGlassOverlay>
  );
}

/**
 * Remaining-time ring: a single one-shot stroke drain over the dwell window —
 * no pulse, no infinite animation (CSS audit Infinite count unchanged).
 */
function SettlementCountdownRing() {
  return (
    <svg aria-hidden="true" className="stage-settlement-ring" viewBox="0 0 20 20">
      <circle className="stage-settlement-ring-track" cx="10" cy="10" r={RING_RADIUS} />
      <circle
        className="stage-settlement-ring-remaining"
        cx="10"
        cy="10"
        r={RING_RADIUS}
        style={{
          animationDuration: `${SETTLEMENT_DWELL_MS}ms`,
          strokeDasharray: RING_CIRCUMFERENCE,
        }}
      />
    </svg>
  );
}
