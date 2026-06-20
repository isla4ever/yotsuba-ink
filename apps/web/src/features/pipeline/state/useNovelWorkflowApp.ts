import { useEffect, useMemo, useState } from 'react';
import { defaultWorkflow } from '../data/defaultWorkflow';
import { consumeEventStream } from '../services/runStream';
import type { CanvasLayout, InspectorTarget, KnowledgeDocument, RunEvent, WorkflowDefinition, WorkflowStage } from '../types/workflow';
import { listKnowledgeDocuments } from '../utils/knowledgeBase';
import { updateStageInputDefault } from '../utils/stageConfig';
import { applyQualityMode, formatResult, stageInputDefaults, updateCanvasLayout, updateStage } from '../utils/workflow';
import { hasOnlineTextProvider, saveCanvasLayoutLocally, saveQualityModeLocally, workflowWithStoredPreferences } from './storage';

type ThemeMode = 'dark' | 'light';
type SaveStatus = 'idle' | 'saving' | 'saved' | 'failed';

export function useNovelWorkflowApp() {
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(() => workflowWithStoredPreferences(defaultWorkflow));
  const [booted, setBooted] = useState(false);
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
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [workspacePhase, setWorkspacePhase] = useState<'planning' | 'running'>('planning');
  const [approvalDraft, setApprovalDraft] = useState('');
  const [approvalPending, setApprovalPending] = useState(false);
  const [selectedInspectorTarget, setSelectedInspectorTarget] = useState<InspectorTarget>({ kind: 'stage', id: workflow.nodes[0].id });
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('novel-workflow-theme');
    if (stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });

  const selectedStage = useMemo(
    () => workflow.nodes.find((stage) => stage.id === selectedId) ?? workflow.nodes[0],
    [selectedId, workflow.nodes],
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('novel-workflow-theme', theme);
  }, [theme]);

  useEffect(() => {
    void refreshKnowledgeDocuments();
  }, []);

  useEffect(() => {
    if (!booted) {
      setBooted(true);
      return;
    }
    setSaveStatus('saving');
    const timer = window.setTimeout(() => {
      void saveWorkflow(workflow);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [workflow]);

  async function saveWorkflow(target = workflow) {
    try {
      await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(target),
      });
      setSaveStatus('saved');
    } catch {
      setSaveStatus('failed');
    }
  }

  async function refreshKnowledgeDocuments() {
    setKnowledgeDocuments(await listKnowledgeDocuments());
  }

  function applyEvent(event: RunEvent) {
    if (event.run_id) setActiveRunId(event.run_id);
    setEvents((items) => [event, ...items].slice(0, 80));
    if (event.type === 'run_blocked') {
      setKnowledgePrompt(event.reason ?? '当前知识库为空，请先上传资料。');
      setKnowledgePromptOpen(true);
      setLatestResult(event.reason ?? '运行被知识库阻断');
    }
    if (event.type === 'node_started' && event.node_id) {
      setWorkspacePhase('running');
      setSelectedId(event.node_id);
      setSelectedInspectorTarget({ kind: 'stage', id: event.node_id });
    }
    if (event.type === 'approval_required') {
      setWorkspacePhase('running');
      setSelectedId(event.node_id ?? 'info');
      setSelectedInspectorTarget({ kind: 'stage', id: event.node_id ?? 'info' });
      setApprovalPending(true);
      setApprovalDraft(formatResult(event.artifact ?? event.result ?? ''));
      setLatestResult('创作立项已生成，等待人工定稿确认。');
    }
    if (event.type === 'artifact_approved') {
      setApprovalPending(false);
      setApprovalDraft(formatResult(event.artifact ?? ''));
      setLatestResult('创作立项已定稿，流水线继续推进。');
    }
    if (event.type === 'brief_regenerated') {
      setApprovalDraft(formatResult(event.artifact ?? ''));
      setLatestResult('已换一版创作立项草稿，等待确认。');
    }
    if (event.type === 'phase_changed' && event.node_id) {
      setWorkspacePhase('running');
      setSelectedId(event.node_id);
      setSelectedInspectorTarget({ kind: 'stage', id: event.node_id });
    }
    if (event.type === 'memory_context_loaded' || event.type === 'memory_writeback_completed') {
      setMemoryEvents((items) => [event, ...items].slice(0, 40));
    }
    if (event.type === 'run_paused') {
      setPaused(true);
      setRunning(false);
      setLatestResult('已在安全点暂停，可调整模式后继续。');
    }
    if (event.type === 'run_resumed') {
      setPaused(false);
      setRunning(true);
      setLatestResult('已恢复创作。');
    }
    if (event.type === 'quality_check_completed') {
      setLatestResult(
        event.quality_report
          ? `质量校验完成：Q ${event.quality_report.score.toFixed(2)}，发现 ${event.quality_report.findings.length} 个问题。`
          : formatResult(event.quality ?? event),
      );
    }
    if (event.type === 'revision_directive_created') {
      setLatestResult(`已生成局部修订指令：${event.directive?.issue ?? '质量问题待修复'}`);
    }
    if (event.type === 'manual_intervention_required') {
      setRunning(false);
      setPaused(true);
      setLatestResult(event.reason ?? '发现不可自动修复的质量阻断，需要人工处理。');
    }
    if (event.type === 'chapter_progress_updated') {
      setLatestResult(`正文进度已更新：${event.chapters?.filter((item) => item.status === 'completed').length ?? 0}/${event.chapters?.length ?? 0} 章`);
    }
    if (event.type === 'node_completed') setLatestResult(formatResult(event.result));
    if (event.type === 'node_failed') setLatestResult(event.error ?? '节点失败');
  }

  async function runWorkflow() {
    if (paused && activeRunId) {
      await fetch(`/api/runs/${activeRunId}/resume`, { method: 'POST' });
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
    await saveWorkflow(workflow);
    const inputs = {
      title: '雾港旧声',
      theme: '悬疑、记忆、旧港、群像',
      quality_mode: workflow.quality_mode,
      stage_configs: Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stageInputDefaults(stage)])),
    };
    const response = await fetch('/api/runs/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_id: workflow.id, inputs }),
    });
    await consumeEventStream(response, applyEvent);
    setRunning(false);
    setPaused(false);
  }

  async function pauseRun() {
    if (!activeRunId) return;
    await fetch(`/api/runs/${activeRunId}/pause`, { method: 'POST' });
  }

  async function approveBrief(artifact: string) {
    if (!activeRunId) return;
    setApprovalPending(false);
    await fetch(`/api/runs/${activeRunId}/approve-artifact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: 'info', output_key: 'info_recommend', artifact }),
    });
  }

  async function regenerateBrief() {
    if (!activeRunId || !approvalPending) return;
    const inputs = {
      title: '雾港旧声',
      theme: '悬疑、记忆、旧港、群像',
      quality_mode: workflow.quality_mode,
      stage_configs: Object.fromEntries(workflow.nodes.map((stage) => [stage.id, stageInputDefaults(stage)])),
    };
    const response = await fetch(`/api/runs/${activeRunId}/regenerate-brief`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_id: workflow.id, inputs }),
    });
    const payload = await response.json();
    if (payload?.artifact) applyEvent({ type: 'brief_regenerated', run_id: activeRunId, node_id: 'info', node_type: 'info_recommend', artifact: payload.artifact });
  }

  function handleStageChange(stage: WorkflowStage) {
    setWorkflow((current) => updateStage(current, stage));
  }

  function handleLayoutChange(layout: CanvasLayout) {
    saveCanvasLayoutLocally(layout);
    setWorkflow((current) => updateCanvasLayout(current, layout));
  }

  function handleAddModelOption(providerId: string, model: string) {
    setWorkflow((current) => ({
      ...current,
      provider_profiles: current.provider_profiles.map((provider) => (
        provider.id === providerId
          ? { ...provider, model_options: Array.from(new Set([...(provider.model_options ?? []), model])) }
          : provider
      )),
    }));
  }

  function handleKnowledgeDocumentDeleted(docId: string) {
    setWorkflow((current) => ({
      ...current,
      nodes: current.nodes.map((stage) => {
        if (stage.id !== 'info') return stage;
        const currentIds = stageInputDefaults(stage).knowledge_base_doc_ids;
        const nextIds = Array.isArray(currentIds) ? currentIds.filter((item) => item !== docId) : [];
        return updateStageInputDefault(stage, 'knowledge_base_doc_ids', nextIds);
      }),
    }));
  }

  function handleQualityModeChange(mode: WorkflowDefinition['quality_mode']) {
    if (running && !paused) return;
    saveQualityModeLocally(mode);
    setWorkflow((current) => applyQualityMode(current, mode));
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
