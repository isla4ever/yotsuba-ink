import { Suspense, lazy } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { QualityMonitorPanel } from './insights/QualityMonitorPanel';
import { RunConsole } from './RunConsole';
import { WikiMemoryPanel } from './insights/WikiMemoryPanel';
import { WorldbuildingPanel } from '../planning/insights/WorldbuildingPanel';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { StageRunMain } from './StageRunMain';

const CharacterForceGraphPanel = lazy(async () => {
  const module = await import('./insights/CharacterForceGraphPanel');
  return { default: module.CharacterForceGraphPanel };
});

type Props = {
  events: RunEvent[];
  memoryEvents: RunEvent[];
  workflow: WorkflowDefinition;
  activeStage: WorkflowStage;
  approvalDraft: string;
  approvalPending: boolean;
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => void;
  onRegenerateBrief: () => void;
};

export function StageRunWorkbench({
  approvalDraft,
  approvalPending,
  events,
  memoryEvents,
  onApprovalDraftChange,
  onApproveBrief,
  onRegenerateBrief,
  workflow,
  activeStage,
}: Props) {
  const latest = events.find((event) => event.type === 'node_completed' || event.type === 'quality_check_completed' || event.type === 'node_failed');
  return (
    <section className="stage-run-workbench">
      <AnimatePresence mode="wait">
        <motion.section
          animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
          className="stage-run-main"
          exit={{ opacity: 0, x: -18, filter: 'blur(8px)' }}
          initial={{ opacity: 0, x: 18, filter: 'blur(8px)' }}
          key={activeStage.id}
          transition={{ duration: 0.28, ease: 'easeOut' }}
        >
          <StageRunMain
            approvalDraft={approvalDraft}
            approvalPending={approvalPending}
            events={events}
            onApprovalDraftChange={onApprovalDraftChange}
            onApproveBrief={onApproveBrief}
            onRegenerateBrief={onRegenerateBrief}
            stage={activeStage}
            workflow={workflow}
          />
          <RunConsole
            collapsed
            events={events}
            latestResult={latest?.error ?? (latest?.result ? JSON.stringify(latest.result) : '创作过程中')}
            memoryEvents={memoryEvents}
            onToggle={() => undefined}
          />
        </motion.section>
      </AnimatePresence>
      <aside className="stage-run-side">
        <Suspense fallback={<GraphPanelFallback />}>
          <CharacterForceGraphPanel events={events} />
        </Suspense>
        <WorldbuildingPanel events={events} />
        <WikiMemoryPanel events={[...events, ...memoryEvents]} />
        <QualityMonitorPanel events={events} stages={workflow.nodes} />
      </aside>
    </section>
  );
}

function GraphPanelFallback() {
  return (
    <section className="insight-card graph-panel-fallback" aria-live="polite">
      <div className="insight-card-head">
        <div>
          <p className="eyebrow">Character Graph</p>
          <h3>人物关系网加载中...</h3>
        </div>
      </div>
    </section>
  );
}
