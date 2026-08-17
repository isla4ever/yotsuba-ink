import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { monitorRoute, routeForStage, type PipelinePhase } from '../lib/stageRoutes';
import { canNavigateToStage, type ModeRoutePolicy } from './runPresentationState';
import type { InspectorTarget } from '../contracts';

type Params = {
  routePhase: PipelinePhase;
  routePolicy: ModeRoutePolicy;
  routeStageId: string;
  /** A run (live or terminal) is attached: the monitor console has content. */
  runAttached: boolean;
  selectedId: string;
  setRunStageNavigator: (navigator: (stageId: string) => void) => void;
  setSelectedId: (stageId: string) => void;
  setSelectedInspectorTarget: (target: InspectorTarget) => void;
  setWorkspacePhase: (phase: 'planning' | 'running') => void;
  workspacePhase: 'planning' | 'running';
};

/** Route → run-state synchronization for the app shell (moved out of App.tsx unchanged). */
export function usePipelineShellRouting({
  routePhase,
  routePolicy,
  routeStageId,
  runAttached,
  selectedId,
  setRunStageNavigator,
  setSelectedId,
  setSelectedInspectorTarget,
  setWorkspacePhase,
  workspacePhase,
}: Params) {
  const navigate = useNavigate();

  useEffect(() => {
    setRunStageNavigator((stageId) => {
      if (!canNavigateToStage(routePolicy, stageId)) {
        // Fast mode has no per-stage workbench routes: run start and stage
        // transitions land on the global monitor console instead.
        if (routePolicy.monitor === 'default') navigate(monitorRoute, { replace: false });
        return;
      }
      navigate(routeForStage(stageId), { replace: false });
    });
  }, [navigate, routePolicy, setRunStageNavigator]);

  useEffect(() => {
    if (routePhase === 'running' && !canNavigateToStage(routePolicy, routeStageId)) {
      navigate(routePolicy.monitor !== 'none' && runAttached ? monitorRoute : '/planning', { replace: true });
    }
  }, [navigate, routePhase, routePolicy, routeStageId, runAttached]);

  useEffect(() => {
    // The monitor console is a run surface: without a run it has nothing to
    // show, and deep mode promises item-by-item review instead of monitoring.
    if (routePhase !== 'monitor') return;
    if (!runAttached || routePolicy.monitor === 'none') {
      navigate(runAttached && routePolicy.stageRoutes === 'all' ? routeForStage(selectedId) : '/planning', { replace: true });
      return;
    }
    if (workspacePhase !== 'running') setWorkspacePhase('running');
  }, [navigate, routePhase, routePolicy, runAttached, setWorkspacePhase, workspacePhase]);

  useEffect(() => {
    // Studio, history, knowledge, settings, and Story Bible are browse routes:
    // they never redirect, never touch stage selection, and stay reachable
    // before any run has started. Monitor has its own dedicated effect above.
    if (routePhase !== 'planning' && routePhase !== 'running') return;
    if (routePhase === 'planning') {
      if (runAttached) {
        if (workspacePhase !== 'running') setWorkspacePhase('running');
        navigate(routePolicy.monitor === 'default' ? monitorRoute : routeForStage(selectedId), { replace: true });
        return;
      }
      if (workspacePhase !== 'planning') setWorkspacePhase('planning');
      return;
    }
    if (!runAttached) {
      if (selectedId !== 'brief') {
        setSelectedId('brief');
        setSelectedInspectorTarget({ kind: 'stage', id: 'brief' });
      }
      if (workspacePhase !== 'planning') setWorkspacePhase('planning');
      navigate('/planning', { replace: true });
      return;
    }
    if (routeStageId && selectedId !== routeStageId) {
      setSelectedId(routeStageId);
      setSelectedInspectorTarget({ kind: 'stage', id: routeStageId });
    }
    if (workspacePhase !== 'running') setWorkspacePhase('running');
  }, [navigate, routePhase, routePolicy, routeStageId, runAttached, selectedId, setSelectedId, setSelectedInspectorTarget, setWorkspacePhase, workspacePhase]);
}
