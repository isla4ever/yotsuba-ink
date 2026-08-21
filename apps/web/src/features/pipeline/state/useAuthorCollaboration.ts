import type { AppendMessage } from '@assistant-ui/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  ArtifactPatchCandidate,
  CollaborationContextPreviewInput,
  CollaborationContextPolicy,
  CollaborationContextReceipt,
  CollaborationMode,
  CollaborationSettings,
  CollaborationStageId,
  CollaborationThread,
  CollaborationThreadDetail,
  SelectionAnchor,
} from "../contracts/authorCollaboration"
import type { KnowledgeDocument } from "../contracts/knowledge"
import { defaultCollaborationUnit, type CollaborationUnitScope } from '../lib/authorCollaborationProjection';
import {
  acceptCollaborationPatch,
  AuthorCollaborationApiError,
  cancelCollaborationTurn,
  createCollaborationThread,
  createCollaborationTurn,
  deleteCollaborationThread,
  getCollaborationSettings,
  getCollaborationThread,
  listCollaborationThreads,
  previewCollaborationContext,
  rejectCollaborationPatch,
  updateCollaborationThread,
} from '../services/authorCollaborationApi';
import {
  appendMessageText,
  collaborationErrorMessage,
  collaborationThreadMatchesScope,
  type PendingCollaborationSubmission,
} from "../lib/authorCollaborationState"
import { useCollaborationComposerDrafts } from "./useCollaborationComposerDrafts"
import { useCollaborationStream } from "./useCollaborationStream"

type Params = {
  activeUnit?: CollaborationUnitScope;
  artifactText: string;
  enabled: boolean;
  knowledgeDocuments?: KnowledgeDocument[];
  runId: string;
  sourceRef: string;
  stageId: CollaborationStageId;
};

export function useAuthorCollaboration({ activeUnit, artifactText, enabled, knowledgeDocuments, runId, sourceRef, stageId }: Params) {
  const [threads, setThreads] = useState<CollaborationThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState('');
  const [detail, setDetail] = useState<CollaborationThreadDetail | null>(null);
  const [settings, setSettings] = useState<CollaborationSettings | null>(null);
  const [contextPolicy, setContextPolicy] = useState<CollaborationContextPolicy | null>(null);
  const [mode, setMode] = useState<CollaborationMode>('discuss');
  const [loading, setLoading] = useState(false);
  const [actionPending, setActionPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingSubmission, setPendingSubmission] = useState<PendingCollaborationSubmission | null>(null);
  const [latestReceipt, setLatestReceipt] = useState<CollaborationContextReceipt | null>(null);
  const [acceptedPatchRef, setAcceptedPatchRef] = useState('');
  const mountedRef = useRef(true);
  const noticeTimerRef = useRef(0)
  const knowledgeDocumentIdKey = useMemo(
    () => (knowledgeDocuments ?? []).map((document) => document.doc_id).sort().join('\u0000'),
    [knowledgeDocuments],
  );
  const knowledgeDocumentIds = useMemo(
    () => new Set(knowledgeDocumentIdKey ? knowledgeDocumentIdKey.split('\u0000') : []),
    [knowledgeDocumentIdKey],
  );

  const inferredUnit = useMemo(() => defaultCollaborationUnit(stageId, artifactText), [artifactText, stageId]);
  const defaultUnit = useMemo(
    () => activeUnit ?? inferredUnit,
    [activeUnit?.label, activeUnit?.unitRef, inferredUnit],
  );
  const activeThread = useMemo(
    () => threads.find((thread) => thread.thread_id === activeThreadId) ?? detail?.thread ?? null,
    [activeThreadId, detail?.thread, threads],
  );
  const activeTurn = useMemo(
    () => [...(detail?.turns ?? [])].reverse().find((turn) => ['queued', 'streaming'].includes(turn.status)) ?? null,
    [detail?.turns],
  );
  const {
    clearComposerDraft,
    composerDraft,
    forgetComposerDraft,
    hasComposerDraft,
    restoreComposerDraft,
    setComposerDraft,
  } = useCollaborationComposerDrafts(activeThreadId)

  const refreshThreads = useCallback(async (signal?: AbortSignal) => {
    const records = await listCollaborationThreads(runId, signal);
    if (!mountedRef.current) return records;
    setThreads(records);
    return records;
  }, [runId]);

  const refreshDetail = useCallback(async (threadId = activeThreadId, signal?: AbortSignal) => {
    if (!threadId) return null;
    const record = await getCollaborationThread(runId, threadId, signal);
    if (!mountedRef.current) return record;
    setDetail(record);
    setThreads((current) => current.map((thread) => thread.thread_id === record.thread.thread_id ? record.thread : thread));
    return record;
  }, [activeThreadId, runId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false
      window.clearTimeout(noticeTimerRef.current)
    };
  }, []);

  useEffect(() => {
    if (!enabled || !runId) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setActiveThreadId('');
    setDetail(null);
    setPendingSubmission(null);
    setLatestReceipt(null);
    setAcceptedPatchRef('');
    void Promise.all([
      listCollaborationThreads(runId, controller.signal),
      getCollaborationSettings(controller.signal).catch(() => null),
    ]).then(async ([records, envelope]) => {
      if (controller.signal.aborted) return;
      setThreads(records);
      if (envelope) {
        setSettings(envelope.settings);
        setMode(envelope.settings.default_mode);
        setContextPolicy({
          ...envelope.settings.context_policy,
          source_pack_refs: envelope.settings.context_policy.source_pack_refs.filter((ref) => knowledgeDocumentIds.has(ref)),
        });
      }
      const reusable = records.find((thread) => collaborationThreadMatchesScope(
        thread,
        stageId,
        sourceRef,
        defaultUnit.unitRef,
      ));
      const thread = reusable ?? await createCollaborationThread(runId, {
        stage_id: stageId,
        source_ref: sourceRef || undefined,
        unit_ref: defaultUnit.unitRef,
        label: defaultUnit.label,
        context_policy: envelope?.settings.context_policy,
      });
      if (controller.signal.aborted) return;
      if (!reusable) setThreads((current) => [thread, ...current]);
      setActiveThreadId(thread.thread_id);
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(collaborationErrorMessage(cause));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [defaultUnit.label, defaultUnit.unitRef, enabled, knowledgeDocumentIds, runId, sourceRef, stageId]);

  useEffect(() => {
    setContextPolicy((current) => current ? {
      ...current,
      source_pack_refs: current.source_pack_refs.filter((ref) => knowledgeDocumentIds.has(ref)),
    } : current);
  }, [knowledgeDocumentIds]);

  useEffect(() => {
    if (!enabled || !activeThreadId) {
      setDetail(null);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    void refreshDetail(activeThreadId, controller.signal)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(collaborationErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [activeThreadId, enabled, refreshDetail]);

  const prepareThreadSwitch = useCallback(() => {
    setPendingSubmission(null);
    setLatestReceipt(null);
    setNotice('');
    setError('');
  }, []);

  useCollaborationStream({
    activeThreadId,
    enabled,
    refreshDetail,
    refreshThreads,
    runId,
  })

  const ensureSelectionThread = useCallback(async (selection: SelectionAnchor | null) => {
    const targetSourceRef = selection?.source_ref || sourceRef;
    const targetUnitRef = selection?.unit_ref || defaultUnit.unitRef;
    if (activeThread && collaborationThreadMatchesScope(activeThread, stageId, targetSourceRef, targetUnitRef)) {
      return activeThread;
    }
    const existing = threads.find((thread) => collaborationThreadMatchesScope(
      thread,
      stageId,
      targetSourceRef,
      targetUnitRef,
    ));
    const thread = existing ?? await createCollaborationThread(runId, {
      stage_id: stageId,
      source_ref: targetSourceRef || undefined,
      unit_ref: targetUnitRef,
      label: selection?.preview || defaultUnit.label,
      context_policy: contextPolicy ?? settings?.context_policy,
    });
    if (!existing) setThreads((current) => [thread, ...current]);
    prepareThreadSwitch();
    setActiveThreadId(thread.thread_id);
    return thread;
  }, [activeThread, contextPolicy, defaultUnit.label, defaultUnit.unitRef, prepareThreadSwitch, runId, settings?.context_policy, sourceRef, stageId, threads]);

  const dispatchSubmission = useCallback(async (submission: PendingCollaborationSubmission) => {
    setActionPending(true);
    setError('');
    try {
      await createCollaborationTurn(runId, submission.threadId, {
        ...submission.input,
        preview_signature: submission.receipt.receipt_hash,
      });
      setPendingSubmission(null);
      clearComposerDraft(submission.threadId);
      await Promise.all([refreshDetail(submission.threadId), refreshThreads()]);
    } catch (cause) {
      if (cause instanceof AuthorCollaborationApiError && cause.code === 'context_reconfirmation_required') {
        const receipt = await previewCollaborationContext(runId, submission.threadId, submission.input);
        setLatestReceipt(receipt);
        setPendingSubmission({ ...submission, receipt });
        setNotice('上下文在发送前发生变化，请重新确认回执。');
      } else {
        // Keep the exact client turn id and preview signature available for a
        // deliberate retry. Rebuilding a fresh request here could double bill.
        setPendingSubmission(submission);
        setError(collaborationErrorMessage(cause));
      }
    } finally {
      setActionPending(false);
    }
  }, [clearComposerDraft, refreshDetail, refreshThreads, runId]);

  const submit = useCallback(async (message: AppendMessage, selection: SelectionAnchor | null) => {
    const content = appendMessageText(message);
    if (!content) return;
    if (mode === 'revise' && !selection) {
      setError('改稿模式需要先在当前阶段字段中选择一段文字。');
      return;
    }
    const draftOwnerThreadId = activeThreadId;
    clearComposerDraft(draftOwnerThreadId);
    setActionPending(true);
    setError('');
    let submissionThreadId = draftOwnerThreadId;
    try {
      const thread = await ensureSelectionThread(selection);
      if (!thread) throw new Error('协作线程尚未就绪');
      submissionThreadId = thread.thread_id;
      if (submissionThreadId !== draftOwnerThreadId) clearComposerDraft(submissionThreadId);
      const input: CollaborationContextPreviewInput = {
        client_turn_id: globalThis.crypto?.randomUUID?.() ?? `client-turn-${Date.now()}`,
        mode,
        message: content,
        context_policy: contextPolicy ?? settings?.context_policy,
        selection: selection ?? undefined,
      };
      const receipt = await previewCollaborationContext(runId, thread.thread_id, input);
      const submission = { input, receipt, threadId: thread.thread_id };
      setLatestReceipt(receipt);
      const currentDetail = thread.thread_id === detail?.thread.thread_id ? detail : await getCollaborationThread(runId, thread.thread_id);
      if (currentDetail.thread.turn_count === 0) {
        setPendingSubmission(submission);
      } else {
        if (currentDetail.thread.turn_count === 1) {
          setNotice(`本轮将继续采用 ${receipt.sources.length} 项已确认上下文，约 ${receipt.token_estimate.toLocaleString()} tokens。`);
          window.clearTimeout(noticeTimerRef.current)
          noticeTimerRef.current = window.setTimeout(() => setNotice(''), 3_600);
        }
        await dispatchSubmission(submission);
      }
    } catch (cause) {
      restoreComposerDraft(submissionThreadId, content);
      setError(collaborationErrorMessage(cause));
    } finally {
      setActionPending(false);
    }
  }, [activeThreadId, clearComposerDraft, contextPolicy, detail, dispatchSubmission, ensureSelectionThread, mode, restoreComposerDraft, runId, settings?.context_policy]);

  const switchThread = useCallback((threadId: string) => {
    prepareThreadSwitch();
    setActiveThreadId(threadId);
  }, [prepareThreadSwitch]);

  const newThread = useCallback(async () => {
    setActionPending(true);
    setError('');
    try {
      const thread = await createCollaborationThread(runId, {
        stage_id: stageId,
        source_ref: sourceRef || undefined,
        unit_ref: defaultUnit.unitRef,
        label: defaultUnit.label,
        context_policy: contextPolicy ?? settings?.context_policy,
      });
      setThreads((current) => [thread, ...current]);
      prepareThreadSwitch();
      setActiveThreadId(thread.thread_id);
    } catch (cause) {
      setError(collaborationErrorMessage(cause));
    } finally {
      setActionPending(false);
    }
  }, [contextPolicy, defaultUnit.label, defaultUnit.unitRef, prepareThreadSwitch, runId, settings?.context_policy, sourceRef, stageId]);

  const setContextOption = useCallback((
    key: 'include_author_preferences' | 'include_craft_mechanisms' | 'include_knowledge' | 'include_canon_wiki' | 'include_foreshadow',
    value: boolean,
  ) => {
    setContextPolicy((current) => current ? { ...current, [key]: value } : current);
  }, []);

  const toggleKnowledgeSource = useCallback((docId: string) => {
    if (!knowledgeDocumentIds.has(docId)) return;
    setContextPolicy((current) => {
      if (!current) return current;
      const alreadySelected = current.source_pack_refs.includes(docId);
      const selectedRefs = alreadySelected
        ? current.source_pack_refs.filter((ref) => ref !== docId)
        : [...current.source_pack_refs, docId];
      return {
        ...current,
        include_knowledge: selectedRefs.length > 0 || current.include_knowledge,
        source_pack_refs: selectedRefs,
      };
    });
  }, [knowledgeDocumentIds]);

  const renameThread = useCallback(async (threadId: string, title: string) => {
    const record = await updateCollaborationThread(runId, threadId, { title });
    setThreads((current) => current.map((thread) => thread.thread_id === threadId ? record : thread));
    if (detail?.thread.thread_id === threadId) setDetail((current) => current ? { ...current, thread: record } : current);
  }, [detail?.thread.thread_id, runId]);

  const archiveThread = useCallback(async (threadId: string) => {
    setActionPending(true);
    try {
      await updateCollaborationThread(runId, threadId, { status: 'archived' });
      const records = await refreshThreads();
      const next = records?.find((thread) => collaborationThreadMatchesScope(
        thread,
        stageId,
        sourceRef,
        defaultUnit.unitRef,
      ));
      if (threadId === activeThreadId) {
        if (next) {
          prepareThreadSwitch();
          setActiveThreadId(next.thread_id);
        }
        else await newThread();
      }
    } catch (cause) {
      setError(collaborationErrorMessage(cause));
    } finally {
      setActionPending(false);
    }
  }, [activeThreadId, defaultUnit.unitRef, newThread, prepareThreadSwitch, refreshThreads, runId, sourceRef, stageId]);

  const removeThread = useCallback(async (threadId: string) => {
    setActionPending(true);
    try {
      await deleteCollaborationThread(runId, threadId);
      forgetComposerDraft(threadId)
      const records = await refreshThreads();
      if (threadId === activeThreadId) {
        const next = records?.find((thread) => collaborationThreadMatchesScope(
          thread,
          stageId,
          sourceRef,
          defaultUnit.unitRef,
        ));
        if (next) {
          prepareThreadSwitch();
          setActiveThreadId(next.thread_id);
        }
        else await newThread();
      }
    } catch (cause) {
      setError(collaborationErrorMessage(cause));
    } finally {
      setActionPending(false);
    }
  }, [activeThreadId, defaultUnit.unitRef, forgetComposerDraft, newThread, prepareThreadSwitch, refreshThreads, runId, sourceRef, stageId]);

  const cancel = useCallback(async () => {
    if (!activeTurn || !activeThreadId) return;
    setActionPending(true);
    try {
      await cancelCollaborationTurn(runId, activeThreadId, activeTurn.turn_id);
      await refreshDetail(activeThreadId);
    } catch (cause) {
      setError(collaborationErrorMessage(cause));
    } finally {
      setActionPending(false);
    }
  }, [activeThreadId, activeTurn, refreshDetail, runId]);

  const decidePatch = useCallback(async (patch: ArtifactPatchCandidate, decision: 'accept' | 'reject') => {
    setActionPending(true);
    setError('');
    try {
      const resolved = decision === 'accept'
        ? await acceptCollaborationPatch(runId, patch.patch_id)
        : await rejectCollaborationPatch(runId, patch.patch_id);
      if (decision === 'accept' && resolved.status === 'accepted') {
        setAcceptedPatchRef(`${resolved.patch_id}:${resolved.writeback_ref}`);
      }
      await Promise.all([refreshDetail(patch.thread_id), refreshThreads()]);
    } catch (cause) {
      setError(collaborationErrorMessage(cause));
    } finally {
      setActionPending(false);
    }
  }, [refreshDetail, refreshThreads, runId]);

  const dismissPendingSubmission = useCallback(() => {
    if (pendingSubmission) {
      restoreComposerDraft(pendingSubmission.threadId, pendingSubmission.input.message);
    }
    setPendingSubmission(null);
  }, [pendingSubmission, restoreComposerDraft]);

  return {
    actionPending,
    acceptedPatchRef,
    activeThread,
    activeThreadId,
    activeTurn,
    archiveThread,
    cancel,
    clearError: () => setError(''),
    confirmPendingSubmission: () => pendingSubmission ? dispatchSubmission(pendingSubmission) : Promise.resolve(),
    composerDraft,
    contextPolicy,
    deleteThread: removeThread,
    detail,
    dismissPendingSubmission,
    error,
    isStreaming: Boolean(activeTurn),
    hasComposerDraft,
    latestReceipt,
    loading,
    mode,
    newThread,
    notice,
    patchDecision: decidePatch,
    pendingSubmission,
    renameThread,
    setMode,
    setComposerDraft,
    setContextOption,
    sourceRef: activeThread && collaborationThreadMatchesScope(activeThread, stageId, sourceRef, activeThread.scope.unit_ref)
      ? activeThread.scope.source_ref
      : sourceRef,
    submit,
    switchThread,
    threads,
    toggleKnowledgeSource,
  };
}

export type AuthorCollaborationController = ReturnType<typeof useAuthorCollaboration>;
