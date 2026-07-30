import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { routeForStage } from '../lib/stageRoutes';
import { canNavigateToStage, type ModeRoutePolicy } from './runPresentationState';
import type { InspectorTarget } from '../contracts';

type Params = {
  cockpitVisible: boolean;
  routePhase: 'studio' | 'history' | 'planning' | 'running' | 'bible';
  routePolicy: ModeRoutePolicy;
  routeStageId: string;
  runHasStarted: boolean;
  selectedId: string;
  setRunStageNavigator: (navigator: (stageId: string) => void) => void;
  setSelectedId: (stageId: string) => void;
  setSelectedInspectorTarget: (target: InspectorTarget) => void;
  setWorkspacePhase: (phase: 'planning' | 'running') => void;
  workspacePhase: 'planning' | 'running';
};

/** Route → run-state synchronization for the app shell (moved out of App.tsx unchanged). */
export function usePipelineShellRouting({
  cockpitVisible,
  routePhase,
  routePolicy,
  routeStageId,
  runHasStarted,
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
      if (!canNavigateToStage(routePolicy, stageId)) return;
      navigate(routeForStage(stageId), { replace: false });
    });
  }, [navigate, routePolicy, setRunStageNavigator]);

  useEffect(() => {
    if (routePhase === 'running' && !canNavigateToStage(routePolicy, routeStageId)) {
      navigate('/planning', { replace: true });
    }
  }, [navigate, routePhase, routePolicy, routeStageId]);

  useEffect(() => {
    // Studio, history, and Story Bible are browse routes: they never redirect, never touch
    // stage selection, and stay reachable before any run has started.
    if (routePhase === 'bible' || routePhase === 'history' || routePhase === 'studio') return;
    if (routePhase === 'planning') {
      if (cockpitVisible) {
        if (!runHasStarted && workspacePhase !== 'planning') setWorkspacePhase('planning');
        return;
      }
      if (workspacePhase !== 'planning') setWorkspacePhase('planning');
      return;
    }
    if (!runHasStarted) {
      if (selectedId !== 'info') {
        setSelectedId('info');
        setSelectedInspectorTarget({ kind: 'stage', id: 'info' });
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
  }, [cockpitVisible, navigate, routePhase, routeStageId, runHasStarted, selectedId, setSelectedId, setSelectedInspectorTarget, setWorkspacePhase, workspacePhase]);
}
