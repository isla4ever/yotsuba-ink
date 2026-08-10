import { useCallback, useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { ProjectRecord, RunHistoryItem, WorkflowDefinition } from '../contracts';
import { getProject } from '../services/projectApi';
import {
  duplicateWorkflowDefinition,
  getDefaultWorkflowDefinition,
  getWorkflowDefinitionById,
} from '../services/workflowApi';
import {
  loadActiveProjectLocally,
  saveActiveProjectLocally,
  setStorageProjectScope,
} from './projectScope';
import { workflowWithStoredPreferences } from './storage';

export type ProjectSessionDeps = {
  cancelInitialRecovery: () => void;
  clearRunState: () => void;
  onHydrated: () => void;
  onWarning: (message: string) => void;
  openRun: (item: RunHistoryItem) => Promise<string>;
  runFacts: {
    activeRunId: string;
    runControlState: string;
    running: boolean;
    selectedId: string;
    workspacePhase: 'planning' | 'running';
  };
  setWorkflow: Dispatch<SetStateAction<WorkflowDefinition>>;
  suppressWorkflowSave: (workflow: WorkflowDefinition) => void;
  workflowId: string;
  workflowName: string;
};

export type OpenProjectResult = { ok: boolean; stageId: string };

/**
 * Phase 11.2 active-project session: owns the storage scope (mine 1), the
 * per-project workflow load (mine 2), the Studio entry path, and the
 * save-as-template action. Call the hook FIRST inside useNovelWorkflowApp so
 * the storage scope is set before any stored-state initializer runs, then
 * populate the collaborators via bind() once they exist (a deps-ref pattern:
 * callbacks read deps at invocation time, never during render).
 */
export function useProjectSession() {
  const [activeProject, setActiveProjectState] = useState<ProjectRecord | null>(() => {
    const stored = loadActiveProjectLocally();
    setStorageProjectScope(stored?.id ?? '');
    return stored;
  });
  const activeProjectRef = useRef(activeProject);
  const depsRef = useRef<ProjectSessionDeps | null>(null);

  const bind = (deps: ProjectSessionDeps) => {
    depsRef.current = deps;
  };

  const applyActiveProject = useCallback((project: ProjectRecord | null) => {
    setStorageProjectScope(project?.id ?? '');
    saveActiveProjectLocally(project);
    activeProjectRef.current = project;
    setActiveProjectState(project);
  }, []);

  /** Align the shell with the project that owns an opened Run. */
  const switchProjectContext = useCallback(async (projectId: string) => {
    if ((activeProjectRef.current?.id ?? '') === projectId) return;
    if (!projectId) throw new Error('Run is missing required project ownership');
    applyActiveProject(await getProject(projectId));
  }, [applyActiveProject]);

  /**
   * Studio entry point: activate a project, load its own workflow and restore
   * its latest run session through the existing read-only open chain.
   * stageId '' means the planning surface.
   */
  const openProject = useCallback(async (project: ProjectRecord, latestRun?: RunHistoryItem | null): Promise<OpenProjectResult> => {
    const deps = depsRef.current;
    if (!deps) return { ok: false, stageId: '' };
    const current = activeProjectRef.current;
    const facts = deps.runFacts;
    const runActive = facts.running || ['starting', 'running', 'stop_requested'].includes(facts.runControlState);
    if (current?.id !== project.id && facts.activeRunId && runActive) {
      deps.onWarning('当前运行仍在执行，请等待进入人工决策点或完成后再切换作品。');
      return { ok: false, stageId: '' };
    }
    if (current?.id === project.id) {
      // Re-entering the live session: no reloads, the shell state is already this project's.
      return { ok: true, stageId: facts.workspacePhase === 'running' ? facts.selectedId : '' };
    }
    deps.cancelInitialRecovery();
    applyActiveProject(project);
    deps.clearRunState();
    if (latestRun && latestRun.can_branch && latestRun.status === 'awaiting_decision') {
      const stageId = await deps.openRun(latestRun);
      if (stageId) return { ok: true, stageId };
    }
    try {
      const loaded = await getWorkflowDefinitionById(project.workflow_id);
      deps.suppressWorkflowSave(loaded);
      deps.setWorkflow(workflowWithStoredPreferences(loaded));
    } catch (error) {
      deps.onWarning(error instanceof Error ? `作品工作流加载失败：${error.message}` : '作品工作流加载失败。');
    }
    return { ok: true, stageId: '' };
  }, [applyActiveProject]);

  /** Sidebar header action: snapshot the current project workflow as a reusable template. */
  const saveWorkflowAsTemplate = useCallback(async () => {
    const deps = depsRef.current;
    if (!deps) return '';
    try {
      const template = await duplicateWorkflowDefinition(deps.workflowId, {
        name: `${activeProjectRef.current?.title ?? deps.workflowName} 模板`,
        is_template: true,
      });
      deps.onWarning('');
      return template.name;
    } catch (error) {
      deps.onWarning(error instanceof Error ? `另存为模板失败：${error.message}` : '另存为模板失败。');
      return '';
    }
  }, []);

  // Boot-time hydration only: load the active project's workflow. Without an
  // active project, the default workflow supports Studio project creation but
  // does not restore or execute an unscoped Run.
  useEffect(() => {
    let active = true;
    const workflowId = activeProjectRef.current?.workflow_id ?? '';
    const load = workflowId
      ? getWorkflowDefinitionById(workflowId).catch(() => getDefaultWorkflowDefinition())
      : getDefaultWorkflowDefinition();
    void load
      .then((loaded) => {
        if (active) depsRef.current?.setWorkflow(workflowWithStoredPreferences(loaded));
      })
      .catch((error) => {
        if (active) depsRef.current?.onWarning(error instanceof Error ? `工作流加载失败：${error.message}` : '工作流加载失败。');
      })
      .finally(() => {
        if (active) depsRef.current?.onHydrated();
      });
    return () => {
      active = false;
    };
  }, []);

  return { activeProject, applyActiveProject, bind, openProject, saveWorkflowAsTemplate, switchProjectContext };
}
