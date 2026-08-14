import { useMemo, useState } from 'react';
import '../styles/entry-core.css';
import { AppHeader } from '../features/pipeline/layout/AppHeader';
import { WorkbenchSidebar } from '../features/pipeline/layout/WorkbenchSidebar';
import { RunningWorkbench } from '../features/pipeline/running/RunningWorkbench';
import { StoryBibleWorkbench } from '../features/pipeline/running/bible/StoryBibleWorkbench';
import { ProviderReadinessProvider } from '../features/pipeline/settings/ProviderReadinessContext';
import { defaultWorkflow } from '../features/pipeline/state/defaultWorkflow';
import { PipelineShellTestProviders } from '../features/pipeline/state/PipelineShellTestProviders';
import type { QualityMode } from '../features/pipeline/contracts';
import { bibleSections, type BibleSection } from '../features/pipeline/lib/stageRoutes';
import { modeRoutePolicy } from '../features/pipeline/state/runPresentationState';
import {
  biblePreviewEvents,
  STAGE_PREVIEW_ORDER,
  stagePreviewEvents,
  type StagePreviewId,
  type StagePreviewPhase,
} from './stagePreviewFixtures';

/**
 * Dev-only offline stage preview (`/__preview/:stage`). Drives the real
 * running workbench with fixture events so design review works in a browser
 * without a backend or provider calls. Excluded from production bundles by
 * the import.meta.env.DEV guard in main.tsx.
 */

const PHASES: StagePreviewPhase[] = ['streaming', 'candidate', 'committed'];
const MODES: QualityMode[] = ['fast', 'balanced', 'deep'];

type PreviewSurface = StagePreviewId | `bible:${BibleSection}`;

function previewSurfaceFromPath(): PreviewSurface {
  const segment = window.location.pathname.split('/')[2] ?? '';
  const bibleSegment = window.location.pathname.split('/')[3] ?? '';
  if (segment === 'bible' && (bibleSections as readonly string[]).includes(bibleSegment)) return `bible:${bibleSegment as BibleSection}`;
  return (STAGE_PREVIEW_ORDER as readonly string[]).includes(segment) ? segment as StagePreviewId : 'brief';
}

export function StagePreviewApp() {
  const [surface, setSurface] = useState<PreviewSurface>(previewSurfaceFromPath);
  const [phase, setPhase] = useState<StagePreviewPhase>('candidate');
  const [mode, setMode] = useState<QualityMode>('balanced');
  const bibleSection = surface.startsWith('bible:') ? surface.slice(6) as BibleSection : null;
  const stageId: StagePreviewId = bibleSection ? 'export' : surface as StagePreviewId;
  const events = useMemo(
    () => (bibleSection ? biblePreviewEvents() : stagePreviewEvents(stageId, phase)),
    [bibleSection, stageId, phase],
  );
  const workflow = useMemo(() => ({ ...defaultWorkflow, quality_mode: mode }), [mode]);
  const stage = workflow.nodes.find((node) => node.id === stageId) ?? workflow.nodes[0];
  const selectSurface = (next: PreviewSurface) => {
    window.history.replaceState(null, '', next.startsWith('bible:') ? `/__preview/bible/${next.slice(6)}` : `/__preview/${next}`);
    setSurface(next);
  };

  return (
    <ProviderReadinessProvider enabled={false} workflowId={workflow.id}>
      <PipelineShellTestProviders
        events={events}
        runState={{
          routeBibleSection: bibleSection ?? '',
          routePhase: bibleSection ? 'bible' : 'running',
          routeStageId: bibleSection ? '' : stageId,
          runHasStarted: true,
          running: !bibleSection && phase === 'streaming',
          selectedStage: stage,
          workspacePhase: 'running',
        }}
        uiCommands={{
          navigateBible: (section) => selectSurface(`bible:${section}`),
          navigateStage: (next) => selectSurface(next as StagePreviewId),
        }}
        workflowConfig={{ qualityMode: mode, routePolicy: modeRoutePolicy(mode, true), workflow }}
      >
        <main className={`product-shell mode-${mode} has-sidebar`}>
          <WorkbenchSidebar />
          <AppHeader sidebarVisible />
          {bibleSection ? (
            <StoryBibleWorkbench section={bibleSection} />
          ) : (
            <RunningWorkbench
              activeRunId=""
              activeStage={stage}
              approvalDraft=""
              approvalPending={false}
              events={events}
              knowledgeDocuments={[]}
              memoryEvents={[]}
              onApprovalDraftChange={() => undefined}
              onApproveBrief={async () => true}
              onContinueSettlement={() => undefined}
              onOpenKnowledgeManager={() => undefined}
              onOpenWorkbench={() => undefined}
              onRegenerateBrief={async () => true}
              onConfirmStageArtifact={async () => true}
              onRegenerateStageDraft={() => undefined}
              settlementDwell={false}
              settlementStageId=""
              workflow={workflow}
            />
          )}
        </main>
        <PreviewSwitcher
          mode={mode}
          onMode={setMode}
          onPhase={setPhase}
          onSurface={selectSurface}
          phase={phase}
          surface={surface}
        />
      </PipelineShellTestProviders>
    </ProviderReadinessProvider>
  );
}

function PreviewSwitcher({ mode, onMode, onPhase, onSurface, phase, surface }: {
  mode: QualityMode;
  onMode: (mode: QualityMode) => void;
  onPhase: (phase: StagePreviewPhase) => void;
  onSurface: (surface: PreviewSurface) => void;
  phase: StagePreviewPhase;
  surface: PreviewSurface;
}) {
  const [open, setOpen] = useState(false);
  const toggleTheme = () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
  };
  if (!open) {
    return (
      <button aria-label="打开预览切换器" onClick={() => setOpen(true)} style={{ ...chipStyle(true), position: 'fixed', right: 10, top: '50%', transform: 'translateY(-50%)', zIndex: 20000 }} type="button">
        ⋮
      </button>
    );
  }
  return (
    <aside style={switcherStyle}>
      <button onClick={() => setOpen(false)} style={chipStyle(false)} type="button">收起</button>
      {STAGE_PREVIEW_ORDER.map((item) => (
        <button key={item} onClick={() => onSurface(item)} style={chipStyle(item === surface)} type="button">{item}</button>
      ))}
      <hr style={{ border: 0, borderTop: '1px solid rgba(255,255,255,0.16)', margin: '2px 0', width: '100%' }} />
      {bibleSections.map((item) => (
        <button key={item} onClick={() => onSurface(`bible:${item}`)} style={chipStyle(surface === `bible:${item}`)} type="button">{item}</button>
      ))}
      <hr style={{ border: 0, borderTop: '1px solid rgba(255,255,255,0.16)', margin: '2px 0', width: '100%' }} />
      {PHASES.map((item) => (
        <button key={item} onClick={() => onPhase(item)} style={chipStyle(item === phase)} type="button">{item}</button>
      ))}
      {MODES.map((item) => (
        <button key={item} onClick={() => onMode(item)} style={chipStyle(item === mode)} type="button">{item}</button>
      ))}
      <button onClick={toggleTheme} style={chipStyle(false)} type="button">theme</button>
    </aside>
  );
}

const switcherStyle: React.CSSProperties = {
  background: 'rgba(10, 14, 13, 0.94)',
  border: '1px solid rgba(255, 255, 255, 0.14)',
  borderRadius: 8,
  display: 'grid',
  gap: 4,
  maxHeight: '86vh',
  overflowY: 'auto',
  padding: 8,
  position: 'fixed',
  right: 10,
  top: '50%',
  transform: 'translateY(-50%)',
  zIndex: 20000,
};

function chipStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? '#2fd68f' : 'transparent',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: 5,
    color: active ? '#06130d' : '#cfd8d4',
    cursor: 'pointer',
    font: '600 11px/1 ui-monospace, monospace',
    padding: '5px 8px',
  };
}
