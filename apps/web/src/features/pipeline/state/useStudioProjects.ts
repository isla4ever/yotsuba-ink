import { useCallback, useEffect, useRef, useState } from 'react';
import type { ProjectRecord, ProjectSummary, WorkflowDefinition } from '../contracts';
import { createProject, listProjects, getProjectSummary } from '../services/projectApi';
import {
  deleteWorkflowDefinition,
  duplicateWorkflowDefinition,
  listWorkflowDefinitions,
  saveWorkflowDefinition,
} from '../services/workflowApi';
import { defaultTemplateId, selectableTemplates } from '../layout/studio/newProjectWizardModel';
import { mapWithConcurrency } from '../layout/studio/studioModel';

const SUMMARY_CONCURRENCY = 4;

/** Studio Shell data controller: project list + summaries, creation, archiving, template management. */
export function useStudioProjects(active: boolean) {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [summaries, setSummaries] = useState<Record<string, ProjectSummary>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [templates, setTemplates] = useState<WorkflowDefinition[]>([]);
  const [templateError, setTemplateError] = useState('');
  const requestSeq = useRef(0);

  const refresh = useCallback(async () => {
    const seq = requestSeq.current + 1;
    requestSeq.current = seq;
    setLoading(true);
    try {
      const list = await listProjects();
      if (requestSeq.current !== seq) return;
      setProjects(list);
      setError('');
      // Summary fan-out is capped at 4 concurrent requests.
      const loaded = await mapWithConcurrency(list, SUMMARY_CONCURRENCY, (project) => getProjectSummary(project.id));
      if (requestSeq.current !== seq) return;
      setSummaries((current) => {
        const next = { ...current };
        loaded.forEach((summary, index) => {
          if (summary) next[list[index].id] = summary;
        });
        return next;
      });
    } catch (reason) {
      if (requestSeq.current !== seq) return;
      setError(reason instanceof Error ? reason.message : '作品库暂时不可用');
    } finally {
      if (requestSeq.current === seq) setLoading(false);
    }
  }, []);

  const refreshTemplates = useCallback(async () => {
    try {
      setTemplates(selectableTemplates(await listWorkflowDefinitions()));
      setTemplateError('');
    } catch (reason) {
      setTemplateError(reason instanceof Error ? reason.message : '工作流模板暂时不可用');
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    void refresh();
    void refreshTemplates();
  }, [active, refresh, refreshTemplates]);

  const create = useCallback(async (input: { title: string; summary: string; templateId: string }) => {
    const project = await createProject({
      title: input.title.trim(),
      summary: input.summary.trim(),
      template_workflow_id: input.templateId || defaultTemplateId,
    });
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
    return project;
  }, []);

  const duplicateTemplate = useCallback(async (workflowId: string, name: string) => {
    try {
      await duplicateWorkflowDefinition(workflowId, { name, is_template: true });
      setTemplateError('');
      await refreshTemplates();
    } catch (reason) {
      setTemplateError(reason instanceof Error ? reason.message : '复制模板失败');
    }
  }, [refreshTemplates]);

  const renameTemplate = useCallback(async (template: WorkflowDefinition, name: string) => {
    const trimmed = name.trim();
    if (!trimmed || trimmed === template.name) return;
    try {
      await saveWorkflowDefinition({ ...template, name: trimmed });
      setTemplateError('');
      await refreshTemplates();
    } catch (reason) {
      setTemplateError(reason instanceof Error ? reason.message : '重命名模板失败');
    }
  }, [refreshTemplates]);

  const removeTemplate = useCallback(async (workflowId: string) => {
    try {
      await deleteWorkflowDefinition(workflowId);
      setTemplateError('');
      await refreshTemplates();
    } catch (reason) {
      // 409 carries the referencing project titles from the backend.
      setTemplateError(reason instanceof Error ? reason.message : '删除模板失败');
    }
  }, [refreshTemplates]);

  return {
    create,
    duplicateTemplate,
    error,
    loading,
    projects,
    refresh,
    refreshTemplates,
    removeTemplate,
    renameTemplate,
    summaries,
    templateError,
    templates,
  };
}

export type StudioProjectsController = ReturnType<typeof useStudioProjects>;
