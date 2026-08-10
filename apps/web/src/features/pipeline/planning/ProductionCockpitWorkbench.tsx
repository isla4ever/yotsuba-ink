import '../../../styles/entry-planning.css';
import { DatabaseZap, Globe2, Settings2, ShieldCheck, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { CharacterForceGraphPanel } from '../running/insights/CharacterForceGraphPanel';
import type { CanvasLayout, InspectorTarget, KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { extractWorldbuilding } from '../lib/stageConfig';
import { stageLabelForUi } from '../lib/display';
import { backdropMotionVariants, overlayExitDurationMs, sheetMotionVariants } from '../lib/motion';
import { CockpitDetailDialog } from './CockpitDetailDialog';
import { CockpitRunLog } from './CockpitRunLog';
import { PipelineCanvas } from './PipelineCanvas';
import { StageInspector } from './StageInspector';
import { activeCockpitStageId, latestNodeStatus, runtimeElapsedSeconds } from './cockpitRuntime';
import { useOverlayDialog } from '../state/useOverlayDialog';

type Props = {
  workflow: WorkflowDefinition;
  selectedId: string;
  selectedStage: WorkflowStage;
  events: RunEvent[];
  knowledgeDocuments: KnowledgeDocument[];
  mode?: 'fast' | 'balanced';
  runHasStarted?: boolean;
  onCanvasSelect: (target: InspectorTarget) => void;
  onLayoutChange: (layout: CanvasLayout) => void;
  onOpenKnowledgeManager: () => void;
  onStageChange: (stage: WorkflowStage) => void;
  onAddModelOption: (providerId: string, model: string) => void;
};

export function ProductionCockpitWorkbench({
  events,
  knowledgeDocuments,
  mode = 'fast',
  runHasStarted = false,
  onCanvasSelect,
  onAddModelOption,
  onLayoutChange,
  onOpenKnowledgeManager,
  onStageChange,
  selectedId,
  selectedStage,
  workflow,
}: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detailPanel, setDetailPanel] = useState<'knowledge' | 'worldbuilding' | 'wiki' | 'quality' | 'stage' | null>(null);
  const [detailStageId, setDetailStageId] = useState(selectedId);
  const [drawerStageId, setDrawerStageId] = useState(selectedId);
  const activeStageId = activeCockpitStageId(events, selectedId, workflow);
  const activeStage = workflow.nodes.find((stage) => stage.id === activeStageId) ?? selectedStage;
  const selectedDrawerStage = workflow.nodes.find((stage) => stage.id === drawerStageId) ?? activeStage;
  const detailStage = workflow.nodes.find((stage) => stage.id === detailStageId) ?? activeStage;
  const runtime = latestNodeStatus(events, activeStage.id);
  const stageStartKey = runtime.startKey;
  const elapsedTick = useElapsedSeconds(stageStartKey);
  const elapsed = runtimeElapsedSeconds(runtime) ?? elapsedTick;
  const world = useMemo(() => extractWorldbuilding(events), [events]);
  const wikiReads = events.filter((event) => event.type === 'evidence.proposed').length;
  const wikiWrites = events.filter((event) => event.type === 'writeback.committed').length;
  const qualityChecks = events.filter((event) => event.type === 'review.completed' || event.type === 'review.unavailable').length;
  const blockedChecks = events.filter((event) => event.type === 'review.unavailable' || event.type === 'decision.required').length;
  const knowledgeChunks = knowledgeDocuments.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
  const referenceEvents = events.filter((event) => event.type.startsWith('rag_') || event.type.startsWith('reference_')).length;
  const wikiStatus = wikiStatusCopy(runHasStarted, wikiReads, wikiWrites);
  const qualityStatus = qualityStatusCopy(runHasStarted, qualityChecks, blockedChecks);
  const worldStatus = runHasStarted ? world.seed || '等待世界观生成' : '启动后可用';
  const closeDrawer = () => setDrawerOpen(false);
  const drawerRef = useOverlayDialog<HTMLElement>({ exitDurationMs: overlayExitDurationMs.sheet, onClose: closeDrawer, open: drawerOpen });

  useEffect(() => {
    if (runHasStarted) setDrawerOpen(false);
  }, [runHasStarted]);

  const handleSelect = (target: InspectorTarget) => {
    if (target.kind !== 'stage') {
      if (runHasStarted) setDetailPanel(target.kind);
      return;
    }
    if (runHasStarted) {
      setDetailStageId(target.id);
      setDetailPanel('stage');
      return;
    }
    setDrawerStageId(target.id);
    onCanvasSelect(target);
    setDrawerOpen(true);
  };

  return (
    <section className={`fast-preview-workbench cockpit-mode-${mode}`}>
      <section className="production-cockpit-canvas-panel">
        <PipelineCanvas
          events={events}
          layoutVariant="cockpit-vertical"
          lockedViewport
          mode="cockpit"
          onLayoutChange={onLayoutChange}
          onSelect={handleSelect}
          runtimeLayersEnabled={runHasStarted}
          selectedId={activeStage.id}
          workflow={workflow}
        />
      </section>

      <section className="fast-runtime-column">
        <CockpitRunLog
          activeStage={activeStage}
          detailAvailable={runHasStarted}
          elapsed={elapsed}
          events={events}
          hasTimer={Boolean(stageStartKey)}
          onOpenStage={() => {
            setDetailStageId(activeStage.id);
            setDetailPanel('stage');
          }}
        />
        <div className="cockpit-widget-grid">
          <button
            className="cockpit-visual-widget wiki-widget"
            disabled={!runHasStarted}
            onClick={() => setDetailPanel('wiki')}
            title={runHasStarted ? '查看 Wiki 事实读写' : '启动创作后可查看 Wiki 事实读写'}
            type="button"
          >
            <span className="cockpit-widget-orb"><DatabaseZap size={18} /></span>
            <span className="cockpit-widget-copy">
              <small>运行状态</small>
              <strong>Wiki 事实层</strong>
              <em>{wikiStatus}</em>
            </span>
            <span className="cockpit-widget-metrics">
              <b>{wikiReads + wikiWrites}</b>
              <small>事件</small>
            </span>
          </button>
          <button
            className="cockpit-visual-widget quality-widget"
            disabled={!runHasStarted}
            onClick={() => setDetailPanel('quality')}
            title={runHasStarted ? '查看质量检查' : '启动创作后可查看质量检查'}
            type="button"
          >
            <span className="cockpit-widget-orb"><ShieldCheck size={18} /></span>
            <span className="cockpit-widget-copy">
              <small>质量检查</small>
              <strong>质量监控</strong>
              <em>{qualityStatus}</em>
            </span>
            <span className="cockpit-widget-metrics">
              <b>{qualityChecks || '0'}</b>
              <small>检查</small>
            </span>
          </button>
        </div>
      </section>

      <section className="fast-observation-column">
        <CharacterForceGraphPanel events={events} qualityMode={mode} surface="bare" />
        <div className="cockpit-side-widget-grid">
          <div className="cockpit-entry-row">
            <button className="cockpit-visual-widget knowledge-widget" onClick={() => setDetailPanel('knowledge')} type="button">
              <span className="cockpit-widget-orb"><DatabaseZap size={18} /></span>
              <span className="cockpit-widget-copy">
                <small>创作依据</small>
                <strong>知识库资料台</strong>
                <em>{knowledgeDocuments.length ? '项目资料已接入前置规划' : '未选项目资料，创作立项不会触发知识库检索'}</em>
              </span>
              <span className="cockpit-widget-metrics">
                <b>{knowledgeDocuments.length}</b>
                <small>{knowledgeChunks || referenceEvents} 片段</small>
              </span>
            </button>
            <button
              className="cockpit-visual-widget world-widget"
              disabled={!runHasStarted}
              onClick={() => setDetailPanel('worldbuilding')}
              title={runHasStarted ? '查看世界观产物' : '启动创作后可查看世界观产物'}
              type="button"
            >
              <span className="cockpit-widget-orb"><Globe2 size={18} /></span>
              <span className="cockpit-widget-copy">
                <small>设定资产</small>
                <strong>世界观</strong>
                <em>{worldStatus}</em>
              </span>
              <span className="cockpit-widget-metrics">
                <b>{world.rules.length}</b>
                <small>硬设定</small>
              </span>
            </button>
          </div>
        </div>
      </section>
      <AnimatePresence>
        {detailPanel ? (
          <CockpitDetailDialog
            documents={knowledgeDocuments}
            events={events}
            kind={detailPanel}
            onClose={() => setDetailPanel(null)}
            stage={detailStage}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {drawerOpen ? (
        <motion.div
          animate="animate"
          className="cockpit-inspector-backdrop app-overlay-backdrop"
          exit="exit"
          initial="initial"
          role="presentation"
          onClick={() => setDrawerOpen(false)}
          variants={backdropMotionVariants}
        >
          <motion.aside
            animate="animate"
            aria-label="阶段配置抽屉"
            aria-modal="true"
            className="cockpit-inspector-drawer app-sheet-surface"
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            ref={drawerRef}
            role="dialog"
            tabIndex={-1}
            variants={sheetMotionVariants}
          >
            <header className="cockpit-inspector-head">
              <div>
                <p>阶段设置</p>
                <h2>{stageLabelForUi(selectedDrawerStage)}</h2>
              </div>
              <button aria-label="关闭阶段配置抽屉" className="cockpit-drawer-close" onClick={() => setDrawerOpen(false)} type="button">
                <X size={18} />
              </button>
            </header>
            <div className="cockpit-inspector-scroll">
              <StageInspector
                inputIdPrefix="cockpit-drawer"
                knowledgeDocuments={knowledgeDocuments}
                qualityMode={workflow.quality_mode}
                stage={selectedDrawerStage}
                providers={workflow.provider_profiles}
                onAddModelOption={onAddModelOption}
                onChange={onStageChange}
                onOpenKnowledgeManager={onOpenKnowledgeManager}
              />
            </div>
          </motion.aside>
        </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}

function useElapsedSeconds(startKey: string) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    setTick(0);
    if (!startKey) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [startKey]);
  return useMemo(() => tick, [tick]);
}

function wikiStatusCopy(runHasStarted: boolean, reads: number, writes: number) {
  if (!runHasStarted) return '启动后可用';
  return reads || writes ? '事实读写正在跟随阶段推进' : '等待真实 Wiki 事件';
}

function qualityStatusCopy(runHasStarted: boolean, checks: number, blocked: number) {
  if (!runHasStarted) return '启动后可用';
  if (!checks) return '等待质量检查事件';
  return blocked ? `${blocked} 个风险需要复核` : '当前质量检查未发现风险';
}
