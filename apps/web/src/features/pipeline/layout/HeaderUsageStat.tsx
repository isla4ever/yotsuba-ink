import { Gauge } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { formatUsageTokens, formatWordTotal, runUsageSignature, runUsageSummary, type RunUsageSummary } from '../lib/runUsage';
import { useRunEventsSelector, useWorkflowConfigContext } from '../state/pipelineShellContext';

/**
 * Phase 12 D6: compact header usage stat — cumulative words plus the 用量额度
 * percentage when the run reports a budget. Click opens a read-only per-stage
 * breakdown. Subscribes to the run-events store (F5) with a signature-equal
 * selector, so streaming deltas never re-render it; renders nothing (no
 * placeholder) until real usage data exists.
 */
export function HeaderUsageStat() {
  const usage = useRunEventsSelector(
    (snapshot) => runUsageSummary(snapshot.events),
    (left, right) => runUsageSignature(left) === runUsageSignature(right),
  );
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const popoverId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && event.target instanceof Node && !rootRef.current.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!usage) return null;

  const summaryParts: string[] = [];
  if (usage.words) summaryParts.push(formatWordTotal(usage.words));
  if (usage.tokens != null) summaryParts.push(`用量 ${formatUsageTokens(usage.tokens)}`);
  if (usage.quotaPercent != null) summaryParts.push(`额度 ${usage.quotaPercent}%`);

  return (
    <div className="header-usage-stat" ref={rootRef}>
      <button
        aria-controls={open ? popoverId : undefined}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="header-usage-trigger"
        onClick={() => setOpen((current) => !current)}
        title="查看各阶段用量明细"
        type="button"
      >
        <Gauge size={13} />
        <span>{summaryParts.join(' · ')}</span>
        {usage.quotaPercent != null ? <QuotaMeter percent={usage.quotaPercent} /> : null}
      </button>
      {open ? <UsagePopover id={popoverId} usage={usage} /> : null}
    </div>
  );
}

/** Meter fill carries severity; the track stays a lighter step of the same ramp. */
function QuotaMeter({ percent }: { percent: number }) {
  const severity = percent >= 100 ? 'exceeded' : percent >= 80 ? 'warning' : 'ok';
  return (
    <i aria-hidden="true" className={`header-usage-meter ${severity}`}>
      <b style={{ width: `${Math.min(100, percent)}%` }} />
    </i>
  );
}

function UsagePopover({ id, usage }: { id: string; usage: RunUsageSummary }) {
  const { workflow } = useWorkflowConfigContext();
  const orderedRows = [...usage.stages].sort((left, right) => stageOrder(left.nodeId) - stageOrder(right.nodeId));
  function stageOrder(nodeId: string) {
    const index = workflow.nodes.findIndex((stage) => stage.id === nodeId);
    return index < 0 ? workflow.nodes.length : index;
  }
  const stageLabel = (nodeId: string) => workflow.nodes.find((stage) => stage.id === nodeId)?.label ?? nodeId;
  const showCost = orderedRows.some((row) => row.costUsd != null);
  return (
    <div aria-label="各阶段用量明细" className="header-usage-popover" id={id} role="dialog">
      <p className="header-usage-popover-title">用量明细（只读）</p>
      <table>
        <thead>
          <tr>
            <th scope="col">阶段</th>
            <th scope="col">用量</th>
            {showCost ? <th scope="col">成本</th> : null}
          </tr>
        </thead>
        <tbody>
          {orderedRows.map((row) => (
            <tr key={row.nodeId}>
              <th scope="row">{stageLabel(row.nodeId)}</th>
              <td>{row.tokens == null ? '暂无' : row.tokens.toLocaleString()}</td>
              {showCost ? <td>{row.costUsd == null ? '—' : `$${row.costUsd.toFixed(3)}`}</td> : null}
            </tr>
          ))}
          <tr className="header-usage-total">
            <th scope="row">合计</th>
            <td>{usage.tokens == null ? '暂无' : usage.tokens.toLocaleString()}</td>
            {showCost ? <td>{usage.costUsd == null ? '—' : `$${usage.costUsd.toFixed(3)}`}</td> : null}
          </tr>
        </tbody>
      </table>
      {usage.quotaPercent != null ? <small>本次运行已使用 {usage.quotaPercent}% 用量额度</small> : null}
    </div>
  );
}
