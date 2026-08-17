import '../../../../styles/entry-running.css';
import { Crosshair, Gauge, PanelRightClose, PanelRightOpen, ShieldCheck } from 'lucide-react';
import { AnimatePresence } from 'motion/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { QualityMode, RunControlState, RunEvent, WorkflowDefinition } from '../../contracts';
import { LoadingOverlay } from '../../layout/LoadingOverlay';
import { RevealText } from '../../layout/RevealText';
import { useReducedMotionPreference } from '../../state/useReducedMotionPreference';
import type { StickyArtifacts } from '../../state/runReducer';
import { MonitorEventFeed } from './MonitorEventFeed';
import { MonitorSidebar, type MonitorSelection } from './MonitorSidebar';
import { MonitorStageBoard } from './MonitorStageBoard';
import { buildMonitorSnapshot } from './monitorModel';
import { loadReadingPosition, saveReadingPosition } from './monitorReadingPosition';
import { useActiveRunDefinition } from '../../state/useActiveRunDefinition';
import { FrozenBindingInventorySheet } from '../FrozenBindingInventorySheet';

type Props = {
  activeRunId: string;
  events: RunEvent[];
  qualityMode: QualityMode;
  runControlState: RunControlState;
  /** Long-run artifact fallback: survives eviction from the capped event buffer. */
  stickyArtifacts: StickyArtifacts;
  workflow: WorkflowDefinition;
  /** Balanced mode: jump back into the per-stage workbench. Fast mode passes undefined. */
  onOpenStageWorkbench?: (stageId: string) => void;
};

/** Entry dwell: the loader holds until the replayed backlog stops arriving. */
const BOOT_MIN_MS = 420;
/** Replay is considered done once no event has landed for this long. */
const BOOT_QUIET_MS = 260;
/** A live run never goes quiet; the loader must not outstay this. */
const BOOT_MAX_MS = 4000;

/**
 * Global run monitor console: the fast-mode default run surface. It owns the
 * shell sidebar slot — the rail is the book skeleton, the center reads content,
 * and the run log lives beside it on the same screen instead of behind a tab.
 */
export function RunMonitorConsole({
  activeRunId,
  events,
  onOpenStageWorkbench,
  qualityMode,
  runControlState,
  stickyArtifacts,
  workflow,
}: Props) {
  const snapshot = useMemo(
    () => buildMonitorSnapshot(events, workflow, stickyArtifacts),
    [events, stickyArtifacts, workflow],
  );
  const reducedMotion = useReducedMotionPreference();
  const [pinned, setPinned] = useState<MonitorSelection | null>(() => loadReadingPosition(activeRunId));
  const [logOpen, setLogOpen] = useState(true);
  const [bindingsOpen, setBindingsOpen] = useState(false);
  const runDefinition = useActiveRunDefinition(activeRunId);
  const booting = useEntryDwell(activeRunId, reducedMotion, events.length);
  const selection: MonitorSelection = pinned ?? { kind: 'stage', stageId: snapshot.activeStageId };
  const stageLabels = useMemo(
    () => Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stage.label])),
    [workflow.nodes],
  );
  const startedAt = useMemo(() => {
    const started = [...events].reverse().find((event) => event.type === 'run.started');
    return started ? Date.parse(started.occurred_at) : Number.NaN;
  }, [events]);
  const terminal = runControlState === 'completed' || runControlState === 'failed';
  const elapsed = useElapsedClock(startedAt, terminal);
  const statusPresentation = runStatusPresentation(runControlState, events);

  useEffect(() => {
    saveReadingPosition(activeRunId, pinned);
  }, [activeRunId, pinned]);

  return (
    <section
      className={`run-monitor-console mode-${qualityMode}${logOpen ? '' : ' log-collapsed'}${booting ? ' is-booting' : ''}`}
      data-run-id={activeRunId}
    >
      <MonitorSidebar
        onSelect={(next) => setPinned(next)}
        selection={selection}
        snapshot={snapshot}
      />

      <div className="monitor-stack">
        <header className="monitor-topbar">
          <div className="monitor-topbar-identity">
            <span className="monitor-topbar-icon"><Gauge size={18} /></span>
            <div>
              <RevealText as="h1" key={snapshot.brief?.title || 'console'} text={snapshot.brief?.title || '创作控制台'} />
              <p>
                <span className={`monitor-run-status ${statusPresentation.tone}`}>{statusPresentation.label}</span>
                {elapsed ? <span>已运行 {elapsed}</span> : null}
                <span>{qualityMode === 'fast' ? '极速模式 · 自动推进' : '平衡模式 · 监控视图'}</span>
              </p>
            </div>
          </div>
          <dl className="monitor-topbar-metrics nw-reveal-stagger">
            <div><dt>累计字数</dt><dd>{snapshot.totals.wordsWritten.toLocaleString()}</dd></div>
            <div><dt>章节定稿</dt><dd>{snapshot.totals.chaptersTotal ? `${snapshot.totals.chaptersDone}/${snapshot.totals.chaptersTotal}` : '—'}</dd></div>
            <div><dt>审稿轮次</dt><dd>{snapshot.totals.reviews || '—'}</dd></div>
            <div><dt>事实写回</dt><dd>{snapshot.totals.writebacks || '—'}</dd></div>
          </dl>
          <button
            className="monitor-frozen-bindings"
            disabled={!runDefinition.definition}
            onClick={() => setBindingsOpen(true)}
            title={runDefinition.error ? '冻结运行定义载入失败' : undefined}
            type="button"
          >
            <ShieldCheck size={14} />
            冻结配置
          </button>
        </header>

        <div className="monitor-body">
          <div className="monitor-center">
            <div className="monitor-center-actions">
              {pinned ? (
                <button className="monitor-follow-button" onClick={() => setPinned(null)} type="button">
                  <Crosshair size={13} />
                  跟随当前进度
                </button>
              ) : <span className="monitor-following-hint">正在跟随当前进度</span>}
              {onOpenStageWorkbench && selection.kind === 'stage' ? (
                <button
                  className="monitor-open-workbench"
                  onClick={() => onOpenStageWorkbench(selection.stageId)}
                  type="button"
                >
                  在阶段工作台中打开
                </button>
              ) : null}
              <button
                aria-expanded={logOpen}
                className="monitor-log-toggle"
                onClick={() => setLogOpen((open) => !open)}
                type="button"
              >
                {logOpen ? <PanelRightClose size={13} /> : <PanelRightOpen size={13} />}
                {logOpen ? '收起运行日志' : '展开运行日志'}
              </button>
            </div>
            <div className="monitor-main" key={selectionKey(selection)}>
              <MonitorStageBoard reading selection={selection} snapshot={snapshot} />
            </div>
          </div>
          <MonitorEventFeed collapsed={!logOpen} events={events} settled={!booting} stageLabels={stageLabels} />
        </div>
      </div>

      <LoadingOverlay
        contained
        detail="正在恢复卷章结构、阶段产物与运行日志。"
        eyebrow="创作控制台"
        open={booting}
        title="正在载入创作现场…"
      />
      <AnimatePresence>
        {bindingsOpen && runDefinition.definition ? (
          <FrozenBindingInventorySheet
            definition={runDefinition.definition}
            onClose={() => setBindingsOpen(false)}
            workflow={workflow}
          />
        ) : null}
      </AnimatePresence>
    </section>
  );
}

function selectionKey(selection: MonitorSelection) {
  return selection.kind === 'chapter' ? `chapter-${selection.chapterRef}` : `stage-${selection.stageId}`;
}

/**
 * Entering a finished run replays hundreds of buffered events. The loader holds
 * until that backlog goes quiet, so the console appears already assembled
 * instead of counting itself up from zero behind the reader.
 */
function useEntryDwell(runId: string, reducedMotion: boolean, eventCount: number) {
  const [booting, setBooting] = useState(!reducedMotion);
  const lastRunRef = useRef(runId);
  const openedAtRef = useRef(Date.now());
  useEffect(() => {
    if (reducedMotion) {
      setBooting(false);
      return undefined;
    }
    if (lastRunRef.current !== runId) {
      lastRunRef.current = runId;
      openedAtRef.current = Date.now();
      setBooting(true);
    }
    if (!booting) return undefined;
    const waited = Date.now() - openedAtRef.current;
    if (waited >= BOOT_MAX_MS) {
      setBooting(false);
      return undefined;
    }
    const wait = Math.min(Math.max(BOOT_QUIET_MS, BOOT_MIN_MS - waited), BOOT_MAX_MS - waited);
    const timer = window.setTimeout(() => setBooting(false), wait);
    return () => window.clearTimeout(timer);
  }, [booting, eventCount, reducedMotion, runId]);
  return booting;
}

function useElapsedClock(startedAt: number, terminal: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (terminal || !Number.isFinite(startedAt)) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [startedAt, terminal]);
  if (!Number.isFinite(startedAt)) return '';
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分 ${seconds % 60} 秒`;
  return `${Math.floor(minutes / 60)} 时 ${minutes % 60} 分`;
}

function runStatusPresentation(state: RunControlState, events: RunEvent[]) {
  if (events.some((event) => event.type === 'run.failed')) return { label: '运行失败', tone: 'failed' };
  if (events.some((event) => event.type === 'run.completed')) return { label: '创作完成', tone: 'done' };
  if (state === 'paused') return { label: '等待决策', tone: 'paused' };
  if (state === 'starting') return { label: '正在启动', tone: 'running' };
  if (state === 'failed') return { label: '运行失败', tone: 'failed' };
  if (state === 'completed') return { label: '创作完成', tone: 'done' };
  return { label: '自动推进中', tone: 'running' };
}
