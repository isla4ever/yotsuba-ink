import { Activity, DatabaseZap, FileCheck2, Save, ShieldCheck } from 'lucide-react';
import type { RunEvent, WorkflowStage } from '../contracts';
import { stageSettlementSummary } from '../lib/stageSettlement';
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
  const summary = stageSettlementSummary(events, stage);
  return (
    <LiquidGlassOverlay className="stage-settlement-overlay" open={open}>
      <div className="stage-settlement-card">
        <p className="eyebrow">阶段结算</p>
        <h2><Activity size={20} />{stage.label} 完成结算</h2>
        <div className="stage-settlement-metrics">
          <span><Save size={13} />{summary.checkpointId ? '检查点已保存' : '等待检查点'}</span>
          <span><FileCheck2 size={13} />{summary.committedArtifact ? 'Artifact 已提交' : 'Artifact 待提交'}</span>
          <span><ShieldCheck size={13} />{summary.reviewCount} 项审稿完成</span>
          <span><DatabaseZap size={13} />写回 {writebackLabel(summary.writebackStatus)}</span>
        </div>
        <p>{summary.unavailableReviewCount ? `${summary.unavailableReviewCount} 个审稿角色不可用，等待 Graph 质量门处理。` : '阶段状态来自 LangGraph 事件与检查点。'}</p>
        <small>Graph 将按已冻结的边继续推进</small>
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

function writebackLabel(status: ReturnType<typeof stageSettlementSummary>['writebackStatus']) {
  return { none: '未触发', queued: '已排队', committed: '已提交', failed: '失败' }[status];
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
