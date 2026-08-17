import { Activity, CheckCircle2, LayoutPanelLeft, MonitorDot, TriangleAlert } from 'lucide-react';
import { memo, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ButtonLoadingIndicator } from './ButtonLoadingIndicator';
import { CreationActionDock } from './CreationActionDock';
import { GlobalToolDock } from './GlobalToolDock';
import { HeaderStageSwitcher } from './HeaderStageSwitcher';
import { ProductNavigationRail } from './ProductNavigationRail';
import { MODE_NOTICE_DWELL_MS, QualityModeTransitionOverlay } from './QualityModeTransitionOverlay';
import { runModeRevealTransition, type ModeRevealOrigin } from './modeRevealTransition';
import { sidebarStageItems } from './workbenchSidebarModel';
import { buildConfigProgress } from '../lib/configProgress';
import { stagePositionEqual, stagePositionSummary } from '../lib/stageProgress';
import { bibleSectionMeta } from '../lib/stageRoutes';
import { useProviderReadinessContext } from '../settings/ProviderReadinessContext';
import { useRunEventsSelector, useRunStateContext, useUICommandContext, useWorkflowConfigContext } from '../state/pipelineShellContext';
import { type StageRunStatus } from '../state/runEventIndex';
import { completedDeliveryStageIds } from '../state/stageDeliveryStatus';
import { canSwitchModeFromFacts } from '../state/runState';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';
import type { QualityMode, WorkflowStage } from '../contracts';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'failed';

type Props = {
  /** Layout decision owned by the parent shell (persistent sidebar breakpoint). */
  sidebarVisible: boolean;
};

/**
 * Memoized (Phase 12 F5): the header reads only low-frequency shell slices;
 * event-driven visuals (stage position, usage stat, budget bar) are leaf
 * components on the run-events store, so streaming deltas leave the header
 * itself untouched.
 */
export const AppHeader = memo(function AppHeader({ sidebarVisible }: Props) {
  const [modeNotice, setModeNotice] = useState<QualityMode | null>(null);
  const reducedMotion = useReducedMotionPreference();
  const providerReadiness = useProviderReadinessContext();
  const run = useRunStateContext();
  const { knowledgeDocuments, qualityMode, routePolicy, saveStatus, workflow } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  const configProgress = useMemo(
    () => buildConfigProgress(workflow, knowledgeDocuments, providerReadiness),
    [knowledgeDocuments, providerReadiness.report, providerReadiness.status, workflow],
  );
  const isRunSurface = run.routePhase === 'running' && run.activeRunId !== '';
  const bibleSurface = run.routePhase === 'bible' && run.routeBibleSection
    ? bibleSectionMeta[run.routeBibleSection]
    : null;
  const headerStageItems = useMemo(
    () => sidebarStageItems({
      policy: routePolicy,
      qualityMode,
      runHasStarted: run.runHasStarted,
      stageRuntimes: run.stageRuntimes,
      stages: workflow.nodes,
    }),
    [qualityMode, routePolicy, run.runHasStarted, run.stageRuntimes, workflow.nodes],
  );
  const showHeaderStageSwitcher = isRunSurface && !sidebarVisible && routePolicy.stageRoutes === 'all';
  const modeSwitchLocked = !canSwitchModeFromFacts({
    approvalPending: run.approvalPending,
    checkpointContinueReady: run.checkpointContinueReady,
    briefContinueReady: run.briefContinueReady,
    paused: run.runControlState === 'paused',
    recoverable: run.runHasStarted,
    runControlState: run.runControlState,
    running: run.running,
  });

  useEffect(() => {
    if (!modeNotice) return;
    const timer = window.setTimeout(() => setModeNotice(null), MODE_NOTICE_DWELL_MS);
    return () => window.clearTimeout(timer);
  }, [modeNotice]);

  const handleQualityModeChange = (mode: QualityMode, origin?: ModeRevealOrigin) => {
    if (mode === qualityMode || modeSwitchLocked) return;
    // State-only switch (no business requests); optionally wrapped in a radial
    // View Transition reveal from the clicked segment. Falls back to instant.
    runModeRevealTransition(
      () => {
        ui.changeQualityMode(mode);
        setModeNotice(mode);
      },
      { origin, reducedMotion },
    );
  };

  const saveStatusLabel = saveStatusCopy[saveStatus];

  return (
    <header className={`app-header ${isRunSurface ? 'run-surface' : ''}${bibleSurface ? ' bible-surface' : ''}`}>
      <div className="header-brand">
        {sidebarVisible ? null : (
          <ProductNavigationRail
            activeItem={ui.activeNavigationItem}
            items={ui.navigationItems}
            onNavigate={ui.navigateProduct}
            onOpenChange={ui.setNavigationOpen}
            open={ui.navigationOpen}
            qualityMode={qualityMode}
          />
        )}
        <div className="brand-mark">YI</div>
        <div>
          <p>Yotsuba Ink</p>
          <strong>长篇创作工作台</strong>
        </div>
      </div>

      <CurrentSurfaceStatus
        configCompleted={configProgress.completed}
        configTotal={configProgress.items.length}
        bibleSurface={bibleSurface}
        isRunSurface={isRunSurface}
        runtimeStatus={run.stageRuntimes[run.selectedStage.id]?.status ?? 'idle'}
        stages={workflow.nodes}
        saveStatus={saveStatus}
        saveStatusLabel={saveStatusLabel}
        stage={run.selectedStage}
        stageSwitcher={showHeaderStageSwitcher ? (
          <HeaderStageSwitcher
            currentStageId={run.selectedStage.id}
            items={headerStageItems}
            onNavigate={ui.navigateStage}
          />
        ) : null}
      />

      <div className="header-actions">
        {/* Attachment, not recoverability: the toggle must survive run.failed /
            run.completed so the terminal console stays reachable. */}
        {run.activeRunId !== '' && routePolicy.monitor !== 'none' ? (
          run.routePhase === 'monitor' ? (
            routePolicy.stageRoutes === 'all' ? (
              <button
                className="header-monitor-toggle"
                onClick={() => ui.navigateStage(run.selectedStage.id)}
                title="返回当前阶段工作台"
                type="button"
              >
                <LayoutPanelLeft size={14} />
                阶段工作台
              </button>
            ) : null
          ) : (
            <button
              className="header-monitor-toggle"
              onClick={ui.openMonitor}
              title="打开创作控制台：卷章结构、内容与运行日志同屏"
              type="button"
            >
              <MonitorDot size={14} />
              创作控制台
            </button>
          )
        ) : null}
        <GlobalToolDock showGlobalEntries={!sidebarVisible} />
        <CreationActionDock disabled={modeSwitchLocked} onQualityModeChange={handleQualityModeChange} />
      </div>
      <QualityModeTransitionOverlay mode={modeNotice} />
    </header>
  );
});

function SaveStatusIcon({ status }: { status: SaveStatus }) {
  if (status === 'saving') return <ButtonLoadingIndicator />;
  if (status === 'failed') return <TriangleAlert size={14} />;
  return <CheckCircle2 size={14} />;
}

function CurrentSurfaceStatus({
  bibleSurface,
  configCompleted,
  configTotal,
  isRunSurface,
  runtimeStatus,
  stages,
  saveStatus,
  saveStatusLabel,
  stage,
  stageSwitcher,
}: {
  bibleSurface: { label: string; detail: string } | null;
  configCompleted: number;
  configTotal: number;
  isRunSurface: boolean;
  runtimeStatus: StageRunStatus;
  stages: WorkflowStage[];
  saveStatus: SaveStatus;
  saveStatusLabel: string;
  stage: WorkflowStage;
  stageSwitcher: ReactNode;
}) {
  const runtimeLabel = runtimeStatus === 'running'
    ? '运行中'
    : runtimeStatus === 'awaiting'
      ? '待决策'
    : runtimeStatus === 'done'
      ? '已完成'
      : runtimeStatus === 'attention'
        ? '待完善'
      : runtimeStatus === 'failed'
        ? '需要复核'
        : '等待运行';
  return (
    <div className={`header-surface-status ${bibleSurface ? 'bible' : isRunSurface ? 'runtime' : 'planning'} ${stageSwitcher ? 'has-stage-switcher' : ''}`}>
      <span className="header-surface-status-icon"><Activity size={15} /></span>
      <div className="header-surface-status-copy">
        <strong>{bibleSurface?.label ?? (isRunSurface ? stage.label : '创作准备')}</strong>
        <span>
          {bibleSurface
            ? 'Story Bible · 只读浏览'
            : isRunSurface
              ? `${runtimeLabel} · 当前工作台`
              : `已完成 ${configCompleted}/${configTotal} 项准备`}
          {isRunSurface ? <HeaderStagePosition currentStageId={stage.id} stages={stages} /> : null}
        </span>
      </div>
      {stageSwitcher}
      <span aria-label={saveStatusLabel} className={`save-state ${saveStatus}`} role="status" title={saveStatusLabel}>
        <SaveStatusIcon status={saveStatus} />
      </span>
    </div>
  );
}

/**
 * Phase 12 D4/Wave 4: the aggregate position uses delivery-truthful stage
 * statuses, so incomplete Cover/Export artifacts do not inflate completion.
 */
function HeaderStagePosition({ currentStageId, stages }: { currentStageId: string; stages: WorkflowStage[] }) {
  const stageIds = useMemo(() => stages.map((stage) => stage.id), [stages]);
  const position = useRunEventsSelector(
    (snapshot) => stagePositionSummary({
      completedStageIds: completedDeliveryStageIds(snapshot.index, stages),
      currentStageId,
      stageIds,
    }),
    stagePositionEqual,
  );
  if (!position.current) return null;
  return (
    <em className="header-stage-position">
      第 {position.current}/{position.total} 阶段{position.completed ? ` · 已完成 ${position.completed}` : ''}
    </em>
  );
}

const saveStatusCopy: Record<SaveStatus, string> = {
  idle: '配置尚未修改',
  saving: '正在自动保存配置',
  saved: '配置已自动保存',
  failed: '配置自动保存失败',
};
