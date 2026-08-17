import { useCallback, useEffect, useMemo, useState } from 'react';
import type { RunEvent } from '../contracts';
import { pendingStageDecision } from '../lib/runDecisionProjection';
import { getStageArtifactDraft, saveStageArtifactDraft } from '../services/runApi';
import type { StageArtifactDraft } from '../running/stageArtifactState';

export const STAGE_DRAFT_AUTOSAVE_MS = 650;

export type StageArtifactDraftSaveStatus =
  | 'idle'
  | 'loading'
  | 'clean'
  | 'dirty'
  | 'saving'
  | 'saved'
  | 'error';

type Options = {
  events: RunEvent[];
  runId: string;
  source: string;
  stageId: string;
};

type DraftBinding = {
  decisionId: string;
  domainRevision: number;
  key: string;
  sourceArtifactId: string;
};

type DraftState = {
  bindingKey: string;
  draft?: StageArtifactDraft;
  error: string;
  localRevision: number;
  status: StageArtifactDraftSaveStatus;
};

const idleState: DraftState = {
  bindingKey: '',
  error: '',
  localRevision: 0,
  status: 'idle',
};

export function useStageArtifactDraft({ events, runId, source, stageId }: Options) {
  const binding = useMemo(
    () => draftBinding(events, runId, stageId),
    [events, runId, stageId],
  );
  const [state, setState] = useState<DraftState>(idleState);

  useEffect(() => {
    if (!binding) {
      setState(idleState);
      return undefined;
    }
    const controller = new AbortController();
    const bindingKey = binding.key;
    setState({
      bindingKey,
      error: '',
      localRevision: 0,
      status: 'loading',
    });
    void getStageArtifactDraft(runId, binding.decisionId, controller.signal)
      .then((record) => {
        setState((current) => {
          if (current.bindingKey !== bindingKey || current.localRevision > 0) return current;
          return {
            bindingKey,
            draft: record
              ? { source, value: JSON.stringify(record.payload, null, 2) }
              : undefined,
            error: '',
            localRevision: 0,
            status: record ? 'saved' : 'clean',
          };
        });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setState((current) => current.bindingKey === bindingKey
          ? { ...current, error: errorMessage(error), status: 'error' }
          : current);
      });
    return () => controller.abort();
  }, [binding, runId, source]);

  useEffect(() => {
    if (!binding || state.bindingKey !== binding.key || state.status !== 'dirty' || !state.draft) {
      return undefined;
    }
    const revision = state.localRevision;
    const value = state.draft.value;
    const timer = window.setTimeout(() => {
      let artifact: Record<string, unknown>;
      try {
        const parsed = JSON.parse(value) as unknown;
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          throw new Error('当前稿不是有效的阶段产物');
        }
        artifact = parsed as Record<string, unknown>;
      } catch (error) {
        setState((current) => current.bindingKey === binding.key
          ? { ...current, error: errorMessage(error), status: 'error' }
          : current);
        return;
      }
      setState((current) => current.bindingKey === binding.key && current.localRevision === revision
        ? { ...current, error: '', status: 'saving' }
        : current);
      void saveStageArtifactDraft(
        runId,
        binding.decisionId,
        binding.domainRevision,
        binding.sourceArtifactId,
        artifact,
      ).then(() => {
        setState((current) => {
          if (current.bindingKey !== binding.key) return current;
          return current.localRevision === revision
            ? { ...current, error: '', status: 'saved' }
            : { ...current, status: 'dirty' };
        });
      }).catch((error: unknown) => {
        setState((current) => {
          if (current.bindingKey !== binding.key) return current;
          return current.localRevision === revision
            ? { ...current, error: errorMessage(error), status: 'error' }
            : { ...current, status: 'dirty' };
        });
      });
    }, STAGE_DRAFT_AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [binding, runId, state]);

  const change = useCallback((changedStageId: string, changedSource: string, value: string) => {
    if (!binding || changedStageId !== stageId || changedSource !== source) return;
    setState((current) => ({
      bindingKey: binding.key,
      draft: { source, value },
      error: '',
      localRevision: current.bindingKey === binding.key ? current.localRevision + 1 : 1,
      status: 'dirty',
    }));
  }, [binding, source, stageId]);

  return {
    change,
    draft: state.bindingKey === binding?.key ? state.draft : undefined,
    error: state.bindingKey === binding?.key ? state.error : '',
    status: state.bindingKey === binding?.key ? state.status : 'idle',
  };
}

function draftBinding(events: RunEvent[], runId: string, stageId: string): DraftBinding | null {
  if (!runId || !stageId) return null;
  const pending = pendingStageDecision(events, stageId);
  const decisionId = textValue(pending?.payload?.decision_id);
  const sourceArtifactId = textValue(pending?.payload?.artifact_ref);
  const domainRevision = pending?.payload?.domain_revision;
  if (!decisionId || !sourceArtifactId || !Number.isInteger(domainRevision) || Number(domainRevision) < 0) {
    return null;
  }
  return {
    decisionId,
    domainRevision: Number(domainRevision),
    key: `${runId}\u0000${stageId}\u0000${decisionId}\u0000${domainRevision}\u0000${sourceArtifactId}`,
    sourceArtifactId,
  };
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '阶段草稿保存失败';
}
