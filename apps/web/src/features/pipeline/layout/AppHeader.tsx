import { Activity, CheckCircle2, TriangleAlert } from 'lucide-react';
import { memo, useEffect, useMemo, useState, type ReactNode } from 'react';
import { BudgetStatusBar } from './BudgetStatusBar';
import { ButtonLoadingIndicator } from './ButtonLoadingIndicator';
import { CreationActionDock } from './CreationActionDock';
import { GlobalToolDock } from './GlobalToolDock';
import { HeaderUsageStat } from './HeaderUsageStat';
import { HeaderStageSwitcher } from './HeaderStageSwitcher';
import { ProductNavigationRail } from './ProductNavigationRail';
import { MODE_NOTICE_DWELL_MS, QualityModeTransitionOverlay } from './QualityModeTransitionOverlay';
import { runModeRevealTransition, type ModeRevealOrigin } from './modeRevealTransition';
import { sidebarStageItems } from './workbenchSidebarModel';
import { buildConfigProgress } from '../lib/configProgress';
import { stagePositionEqual, stagePositionSummary } from '../lib/stageProgress';
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
  const isRunSurface = run.workspacePhase === 'running' && run.runHasStarted;
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
    infoContinueReady: run.infoContinueReady,
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
    <header className={`app-header ${isRunSurface ? 'run-surface' : ''}`}>
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
        <div className="brand-mark">NW</div>
        <div>
          <p>Yotsuba Ink</p>
          <strong>小说流水线平台</strong>
        </div>
      </div>

      <CurrentSurfaceStatus
        configCompleted={configProgress.completed}
        configTotal={configProgress.items.length}
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
        <GlobalToolDock showGlobalEntries={!sidebarVisible} />
        <CreationActionDock disabled={modeSwitchLocked} onQualityModeChange={handleQualityModeChange} />
      </div>
      <QualityModeTransitionOverlay mode={modeNotice} />
      <BudgetStatusBar />
    </header>
  );
});

function SaveStatusIcon({ status }: { status: SaveStatus }) {
  if (status === 'saving') return <ButtonLoadingIndicator />;
  if (status === 'failed') return <TriangleAlert size={14} />;
  return <CheckCircle2 size={14} />;
}

function CurrentSurfaceStatus({
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
    : runtimeStatus === 'done'
      ? '已完成'
      : runtimeStatus === 'attention'
        ? '待完善'
      : runtimeStatus === 'failed'
        ? '需要复核'
        : '等待运行';
  return (
    <div className={`header-surface-status ${isRunSurface ? 'runtime' : 'planning'} ${stageSwitcher ? 'has-stage-switcher' : ''}`}>
      <span className="header-surface-status-icon"><Activity size={15} /></span>
      <div className="header-surface-status-copy">
        <strong>{isRunSurface ? stage.label : '创作准备'}</strong>
        <span>
          {isRunSurface ? `${runtimeLabel} · 当前工作台` : `已完成 ${configCompleted}/${configTotal} 项准备`}
          {isRunSurface ? <HeaderStagePosition currentStageId={stage.id} stages={stages} /> : null}
        </span>
      </div>
      {stageSwitcher}
      <HeaderUsageStat />
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
