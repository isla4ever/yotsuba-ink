import { CheckCircle2, Clock3, FileClock, History, Play, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { ExportReceipt, RunHistoryItem } from '../contracts';
import { formatHistoryTime } from '../lib/display';
import { qualityModeProfiles } from '../lib/qualityModes';
import { useRunStateContext, useUICommandContext } from '../state/pipelineShellContext';
import { useRunExportHistory } from '../state/useRunExportHistory';
import { HistoryExportVersions } from './HistoryExportVersions';
import { LoadingButton } from './LoadingButton';
import { ManuscriptLoadingIndicator } from './ManuscriptLoadingIndicator';
import { StudioMobileNav } from './studio/StudioMobileNav';

export function CreationHistoryPage() {
  const run = useRunStateContext();
  const ui = useUICommandContext();
  const [selectedId, setSelectedId] = useState(run.historyItems[0]?.run_id ?? '');
  const [pendingAction, setPendingAction] = useState('');
  const selected = run.historyItems.find((item) => item.run_id === selectedId) ?? run.historyItems[0];
  const exportHistory = useRunExportHistory(selected?.run_id ?? '', selected?.export_count ?? 0);

  useEffect(() => {
    void ui.refreshHistory();
    // The history route owns its refresh lifecycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId || !run.historyItems.some((item) => item.run_id === selectedId)) {
      setSelectedId(run.historyItems[0]?.run_id ?? '');
    }
  }, [run.historyItems, selectedId]);

  async function runAction(key: string, action: () => Promise<unknown>) {
    setPendingAction(key);
    try {
      await action();
    } finally {
      setPendingAction('');
    }
  }

  return (
    <section aria-labelledby="history-page-title" className="history-page">
      <StudioMobileNav />
      <header className="history-page-head">
        <div>
          <p className="eyebrow">运行追溯</p>
          <h1 id="history-page-title"><History size={20} />创作历史</h1>
          <span>按运行查看阶段进度、稳定快照与交付版本</span>
        </div>
        <LoadingButton className="ghost tiny-action" loading={run.historyLoading} loadingLabel="同步中" onClick={() => void ui.refreshHistory()}>
          <RotateCcw size={14} />刷新
        </LoadingButton>
      </header>

      {run.historyError ? <p className="history-inline-error" role="alert">{presentHistoryError(run.historyError)}</p> : null}
      <div className="history-page-layout">
        <nav aria-label="运行记录" className="history-page-index">
          <div className="history-page-index-head">
            <strong>运行记录</strong>
            <span>{run.historyLoading ? '正在同步' : `${run.historyItems.length} 条`}</span>
          </div>
          {run.historyLoading && !run.historyItems.length ? <HistoryLoading /> : null}
          {!run.historyLoading && !run.historyItems.length ? <HistoryEmpty /> : null}
          {run.historyItems.map((item) => (
            <button
              aria-current={selected?.run_id === item.run_id ? 'true' : undefined}
              className={`history-run-row${selected?.run_id === item.run_id ? ' active' : ''}`}
              key={item.run_id}
              onClick={() => setSelectedId(item.run_id)}
              type="button"
            >
              <span className="history-run-row-icon"><FileClock size={15} /></span>
              <span className="history-run-row-main">
                <strong>{item.title}</strong>
                <small>{statusLabel(item.status)} · {stageLabel(item)}</small>
                <HistoryProgressRail stageId={item.current_stage.id} completed={item.completed_stage_ids} />
              </span>
              <time dateTime={item.updated_at}>{formatHistoryTime(item.updated_at)}</time>
            </button>
          ))}
        </nav>

        {selected ? (
          <article aria-busy={Boolean(pendingAction) || exportHistory.loading} className="history-page-detail" key={selected.run_id}>
            <header className="history-record-head">
              <div>
                <p className="eyebrow">当前记录</p>
                <h2>{selected.title}</h2>
                <span className="history-run-id">{selected.run_id}</span>
              </div>
              <div className="history-record-state">
                <strong>{statusLabel(selected.status)}</strong>
                <span>{qualityModeProfiles[selected.quality_mode].title}模式 · {formatHistoryTime(selected.updated_at)}</span>
              </div>
            </header>

            <HistoryStageTimeline item={selected} />

            <section className="history-record-summary">
              <div><CheckCircle2 size={15} /><strong>{stageLabel(selected)} · 运行快照</strong></div>
              <p>{selected.summary || '当前阶段状态已保存，尚无额外摘要。'}</p>
              <span>{selected.latest_snapshot_id ? `稳定快照 ${selected.latest_snapshot_id.slice(-18)}` : '暂无稳定快照'}</span>
            </section>

            <dl className="history-record-metrics">
              <div><dt>完成字数</dt><dd>{selected.words.toLocaleString()}</dd></div>
              <div><dt>模型用量</dt><dd>{selected.total_tokens.toLocaleString()}</dd></div>
              <div><dt>估算成本</dt><dd>{selected.estimated_cost_usd ? `$${selected.estimated_cost_usd.toFixed(3)}` : '未计价'}</dd></div>
              <div><dt>交付状态</dt><dd>{selected.export_ready ? '已就绪' : '未就绪'}</dd></div>
            </dl>

            <HistoryExportVersions
              error={presentHistoryError(exportHistory.error)}
              fallbackReceipt={selected.latest_export}
              items={exportHistory.items}
              loading={exportHistory.loading}
              onDownload={(receipt: ExportReceipt) => void runAction(
                `download:${selected.run_id}:${receipt.export_id}`,
                () => ui.downloadHistoryExport(selected, receipt),
              )}
              onRefresh={() => void exportHistory.refresh()}
              pendingAction={pendingAction}
            />

            <footer className="history-record-actions">
              {selected.status === 'recovery_required' ? (
                <LoadingButton className="mode-primary-action" disabled={Boolean(pendingAction) || !selected.latest_snapshot_id} loading={pendingAction.startsWith('restore:')} loadingLabel="正在恢复" onClick={() => void runAction(`restore:${selected.run_id}`, () => ui.restoreHistoryCheckpoint(selected))}>
                  <RotateCcw size={14} />恢复稳定检查点
                </LoadingButton>
              ) : selected.status === 'completed' ? null : (
                <LoadingButton className="mode-primary-action" disabled={Boolean(pendingAction) || (selected.status === 'running' && run.activeRunId !== selected.run_id)} loading={pendingAction.startsWith('open:')} loadingLabel="正在打开" onClick={() => void runAction(`open:${selected.run_id}`, () => ui.openHistoryRun(selected))}>
                  <Play size={14} />{run.activeRunId === selected.run_id ? '返回当前运行' : '打开运行'}
                </LoadingButton>
              )}
            </footer>
          </article>
        ) : null}
      </div>
    </section>
  );
}

function HistoryStageTimeline({ item }: { item: RunHistoryItem }) {
  const active = activeStageIndex(item.current_stage.id, item.completed_stage_ids);
  return (
    <ol aria-label={`当前进度：${stageLabel(item)}`} className="history-stage-timeline">
      {stageSteps.map((step, index) => (
        <li className={index < active ? 'done' : index === active ? 'active' : ''} key={step.id}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <strong>{step.label}</strong>
          <small>{index < active ? '已完成' : index === active ? '当前阶段' : '未开始'}</small>
        </li>
      ))}
    </ol>
  );
}

function HistoryProgressRail({ stageId, completed }: { stageId: string; completed: string[] }) {
  const active = activeStageIndex(stageId, completed);
  return <span aria-hidden="true" className="history-progress-rail">{stageSteps.map((step, index) => <i className={index < active ? 'done' : index === active ? 'active' : ''} key={step.id} />)}</span>;
}

function HistoryLoading() {
  return <div className="history-page-empty" role="status"><ManuscriptLoadingIndicator size="compact" /><span>正在同步创作历史</span></div>;
}

function HistoryEmpty() {
  return <div className="history-page-empty" role="status"><Clock3 size={20} /><strong>还没有创作历史</strong><span>完成一次运行后即可在这里追溯。</span></div>;
}

const stageSteps = [
  { id: 'info', label: '立项' }, { id: 'summary', label: '梗概' }, { id: 'outline', label: '大纲' },
  { id: 'detail', label: '细纲' }, { id: 'text', label: '正文' }, { id: 'cover', label: '封面' }, { id: 'export', label: '导出' },
];

function activeStageIndex(stageId: string, completed: string[]) {
  return Math.max(stageIndex(stageId), completed.reduce((max, id) => Math.max(max, stageIndex(id) + 1), 0));
}

function stageIndex(stageId: string) {
  const index = stageSteps.findIndex((stage) => stage.id === stageId);
  return index < 0 ? 0 : index;
}

function stageLabel(item: RunHistoryItem) {
  return item.current_stage.label || stageSteps.find((stage) => stage.id === item.current_stage.id)?.label || '配置准备';
}

function statusLabel(status: RunHistoryItem['status']) {
  return ({ created: '已创建', running: '进行中', paused: '已暂停', awaiting_confirmation: '待确认', recovery_required: '待恢复', failed: '失败', completed: '已完成' } satisfies Record<RunHistoryItem['status'], string>)[status];
}

function presentHistoryError(error: string) {
  if (!error) return '';
  if (/\/exports\b|交付版本/i.test(error)) return '交付版本暂时无法读取，请稍后刷新。';
  if (/request failed|network|fetch/i.test(error)) return '创作历史暂时无法同步，请检查服务状态后重试。';
  return error;
}
