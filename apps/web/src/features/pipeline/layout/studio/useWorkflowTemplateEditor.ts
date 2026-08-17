import { useCallback, useEffect, useRef, useState } from 'react';
import type { WorkflowDefinition, WorkflowStage } from '../../contracts';
import {
  duplicateWorkflowDefinition,
  getWorkflowDefinitionById,
  saveWorkflowDefinition,
} from '../../services/workflowApi';
import { withAddedModelOption, withQualityMode, withUpdatedStage } from '../../state/workflowMutations';

export type TemplateEditorSaveState = 'idle' | 'saving' | 'saved' | 'failed';

const SAVE_DEBOUNCE_MS = 700;

/**
 * Loads one workflow template by id and autosaves edits, mirroring how the
 * per-book workflow saves. Templates are plain workflow definitions, so the
 * same upsert endpoint applies — only the entry surface differs.
 */
export function useWorkflowTemplateEditor(workflowId: string) {
  const [workflow, setWorkflow] = useState<WorkflowDefinition | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<TemplateEditorSaveState>('idle');
  const dirtyRef = useRef(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    dirtyRef.current = false;
    getWorkflowDefinitionById(workflowId)
      .then((loaded) => {
        if (!active) return;
        setWorkflow(loaded);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setWorkflow(null);
        setError(cause instanceof Error ? cause.message : '未能载入该工作流模板。');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [workflowId]);

  useEffect(() => {
    if (!workflow || !dirtyRef.current) return undefined;
    setSaveState('saving');
    const timer = window.setTimeout(() => {
      saveWorkflowDefinition(workflow)
        .then(() => setSaveState('saved'))
        .catch(() => setSaveState('failed'));
    }, SAVE_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [workflow]);

  const edit = useCallback((next: (current: WorkflowDefinition) => WorkflowDefinition) => {
    dirtyRef.current = true;
    setWorkflow((current) => (current ? next(current) : current));
  }, []);

  return {
    addModelOption: useCallback((providerId: string, model: string) => {
      edit((current) => withAddedModelOption(current, providerId, model));
    }, [edit]),
    createOneTimeCopy: useCallback(() => duplicateWorkflowDefinition(workflowId, {
      name: '本书专用创作流水线',
      is_template: false,
    }), [workflowId]),
    error,
    loading,
    renameTemplate: useCallback((name: string) => {
      edit((current) => ({ ...current, name }));
    }, [edit]),
    saveState,
    saveAsTemplate: useCallback((name: string) => duplicateWorkflowDefinition(workflowId, {
      name,
      is_template: true,
    }), [workflowId]),
    setQualityMode: useCallback((mode: WorkflowDefinition['quality_mode']) => {
      edit((current) => withQualityMode(current, mode));
    }, [edit]),
    updateStage: useCallback((stage: WorkflowStage) => {
      edit((current) => withUpdatedStage(current, stage));
    }, [edit]),
    workflow,
  };
}
