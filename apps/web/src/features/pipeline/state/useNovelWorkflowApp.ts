import { useEffect, useMemo, useState } from 'react';
import { defaultWorkflow } from './defaultWorkflow';
import { listKnowledgeDocuments } from '../services/knowledge';
import { approveRunBrief, briefRegeneratedEvent, createRunStream, pauseRunRequest, regenerateRunBrief, resumeRun } from '../services/runApi';
import { consumeEventStream } from '../services/runStream';
import { saveWorkflowDefinition } from '../services/workflowApi';
import type { CanvasLayout, InspectorTarget, KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { applyRunEvent } from './appEvents';
import { buildRunInputs } from './runInputs';
import { hasOnlineTextProvider, saveCanvasLayoutLocally, saveQualityModeLocally, workflowWithStoredPreferences } from './storage';
import { useThemeMode } from './useThemeMode';
import { useWorkflowAutosave } from './useWorkflowAutosave';
import { withAddedModelOption, withDeletedKnowledgeDocument, withQualityMode, withUpdatedCanvasLayout, withUpdatedStage } from './workflowMutations';

export function useNovelWorkflowApp() {
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(() => workflowWithStoredPreferences(defaultWorkflow));
  const [selectedId, setSelectedId] = useState(workflow.nodes[0].id);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [memoryEvents, setMemoryEvents] = useState<RunEvent[]>([]);
  const [latestResult, setLatestResult] = useState('等待运行');
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [activeRunId, setActiveRunId] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [knowledgeManagerOpen, setKnowledgeManagerOpen] = useState(false);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocument[]>([]);
  const [knowledgePromptOpen, setKnowledgePromptOpen] = useState(false);
  const [knowledgePrompt, setKnowledgePrompt] = useState('');
  const [apiWarning, setApiWarning] = useState('');
  const [workspacePhase, setWorkspacePhase] = useState<'planning' | 'running'>('planning');
  const [approvalDraft, setApprovalDraft] = useState('');
  const [approvalPending, setApprovalPending] = useState(false);
  const [selectedInspectorTarget, setSelectedInspectorTarget] = useState<InspectorTarget>({ kind: 'stage', id: workflow.nodes[0].id });
  const { theme, setTheme } = useThemeMode();
  const { saveStatus } = useWorkflowAutosave(workflow, saveWorkflowDefinition);

  const selectedStage = useMemo(
    () => workflow.nodes.find((stage) => stage.id === selectedId) ?? workflow.nodes[0],
    [selectedId, workflow.nodes],
  );
  const runInputs = useMemo(() => buildRunInputs(workflow), [workflow]);

  useEffect(() => {
    void refreshKnowledgeDocuments();
  }, []);

  async function refreshKnowledgeDocuments() {
    setKnowledgeDocuments(await listKnowledgeDocuments());
  }

  function applyEvent(event: RunEvent) {
    applyRunEvent(event, {
      setActiveRunId,
      setEvents,
      setMemoryEvents,
      setKnowledgePrompt,
      setKnowledgePromptOpen,
      setLatestResult,
      setWorkspacePhase,
      setSelectedId,
      setSelectedInspectorTarget,
      setApprovalPending,
      setApprovalDraft,
      setPaused,
      setRunning,
    });
  }

  async function runWorkflow() {
    if (paused && activeRunId) {
      await resumeRun(activeRunId);
      setPaused(false);
      setRunning(true);
      return;
    }
    if (!hasOnlineTextProvider(workflow)) {
      setApiWarning('当前尚未配置线上模型 API。可先配置 OpenAI-compatible Provider 后运行真实生成；也可使用本地演示通道预览流程结构。');
      setSettingsOpen(true);
      return;
    }
    setRunning(true);
    setPaused(false);
    setActiveRunId('');
    setEvents([]);
    setMemoryEvents([]);
    setWorkspacePhase('planning');
    setApprovalDraft('');
    setApprovalPending(false);
    setLatestResult('创作中...');
    await saveWorkflowDefinition(workflow);
    const response = await createRunStream(workflow.id, runInputs);
    await consumeEventStream(response, applyEvent);
    setRunning(false);
    setPaused(false);
  }

  async function pauseRun() {
    if (!activeRunId) return;
    await pauseRunRequest(activeRunId);
  }

  async function approveBrief(artifact: string) {
    if (!activeRunId) return;
    setApprovalPending(false);
    await approveRunBrief(activeRunId, artifact);
  }

  async function regenerateBrief() {
    if (!activeRunId || !approvalPending) return;
    const payload = await regenerateRunBrief(activeRunId, workflow.id, runInputs);
    if (payload?.artifact) applyEvent(briefRegeneratedEvent(activeRunId, payload.artifact));
  }

  function handleStageChange(stage: WorkflowStage) {
    setWorkflow((current) => withUpdatedStage(current, stage));
  }

  function handleLayoutChange(layout: CanvasLayout) {
    saveCanvasLayoutLocally(layout);
    setWorkflow((current) => withUpdatedCanvasLayout(current, layout));
  }

  function handleAddModelOption(providerId: string, model: string) {
    setWorkflow((current) => withAddedModelOption(current, providerId, model));
  }

  function handleKnowledgeDocumentDeleted(docId: string) {
    setWorkflow((current) => withDeletedKnowledgeDocument(current, docId));
  }

  function handleQualityModeChange(mode: WorkflowDefinition['quality_mode']) {
    if (running && !paused) return;
    saveQualityModeLocally(mode);
    setWorkflow((current) => withQualityMode(current, mode));
  }

  function handleCanvasSelect(target: InspectorTarget) {
    setSelectedInspectorTarget(target);
    setSelectedId(target.id);
  }

  return {
    activeRunId,
    apiWarning,
    approvalDraft,
    approvalPending,
    events,
    handleAddModelOption,
    handleCanvasSelect,
    handleKnowledgeDocumentDeleted,
    handleLayoutChange,
    handleQualityModeChange,
    handleStageChange,
    knowledgeDocuments,
    knowledgeManagerOpen,
    knowledgePrompt,
    knowledgePromptOpen,
    latestResult,
    memoryEvents,
    paused,
    refreshKnowledgeDocuments,
    regenerateBrief,
    runWorkflow,
    running,
    saveStatus,
    selectedId,
    selectedInspectorTarget,
    selectedStage,
    setApprovalDraft,
    setApiWarning,
    setKnowledgeManagerOpen,
    setKnowledgeDocuments,
    setKnowledgePromptOpen,
    setSelectedId,
    setSettingsOpen,
    setTheme,
    setWorkflow,
    setWorkspacePhase,
    setRunning,
    settingsOpen,
    theme,
    workflow,
    workspacePhase,
    approveBrief,
    pauseRun,
  };
}
