import { formatResult } from '../lib/workflow';
import type { InspectorTarget, RunEvent } from '../contracts';

type EventSetters = {
  setActiveRunId: (value: string) => void;
  setEvents: (updater: (items: RunEvent[]) => RunEvent[]) => void;
  setMemoryEvents: (updater: (items: RunEvent[]) => RunEvent[]) => void;
  setKnowledgePrompt: (value: string) => void;
  setKnowledgePromptOpen: (value: boolean) => void;
  setLatestResult: (value: string) => void;
  setWorkspacePhase: (value: 'planning' | 'running') => void;
  setSelectedId: (value: string) => void;
  setSelectedInspectorTarget: (value: InspectorTarget) => void;
  setApprovalPending: (value: boolean) => void;
  setApprovalDraft: (value: string) => void;
  setPaused: (value: boolean) => void;
  setRunning: (value: boolean) => void;
};

export function applyRunEvent(event: RunEvent, setters: EventSetters) {
  if (event.run_id) setters.setActiveRunId(event.run_id);
  setters.setEvents((items) => [event, ...items].slice(0, 80));

  if (event.type === 'run_blocked') {
    setters.setKnowledgePrompt(event.reason ?? '当前知识库为空，请先上传资料。');
    setters.setKnowledgePromptOpen(true);
    setters.setLatestResult(event.reason ?? '运行被知识库阻断');
  }

  if (event.type === 'node_started' && event.node_id) {
    syncStageSelection(event.node_id, setters);
  }

  if (event.type === 'approval_required') {
    const nodeId = event.node_id ?? 'info';
    syncStageSelection(nodeId, setters);
    setters.setApprovalPending(true);
    setters.setApprovalDraft(formatResult(event.artifact ?? event.result ?? ''));
    setters.setLatestResult('创作立项已生成，等待人工定稿确认。');
  }

  if (event.type === 'artifact_approved') {
    setters.setApprovalPending(false);
    setters.setApprovalDraft(formatResult(event.artifact ?? ''));
    setters.setLatestResult('创作立项已定稿，流水线继续推进。');
  }

  if (event.type === 'brief_regenerated') {
    setters.setApprovalDraft(formatResult(event.artifact ?? ''));
    setters.setLatestResult('已换一版创作立项草稿，等待确认。');
  }

  if (event.type === 'phase_changed' && event.node_id) {
    syncStageSelection(event.node_id, setters);
  }

  if (event.type === 'memory_context_loaded' || event.type === 'memory_writeback_completed') {
    setters.setMemoryEvents((items) => [event, ...items].slice(0, 40));
  }

  if (event.type === 'run_paused') {
    setters.setPaused(true);
    setters.setRunning(false);
    setters.setLatestResult('已在安全点暂停，可调整模式后继续。');
  }

  if (event.type === 'run_resumed') {
    setters.setPaused(false);
    setters.setRunning(true);
    setters.setLatestResult('已恢复创作。');
  }

  if (event.type === 'quality_check_completed') {
    setters.setLatestResult(
      event.quality_report
        ? `质量校验完成：Q ${event.quality_report.score.toFixed(2)}，发现 ${event.quality_report.findings.length} 个问题。`
        : formatResult(event.quality ?? event),
    );
  }

  if (event.type === 'revision_directive_created') {
    setters.setLatestResult(`已生成局部修订指令：${event.directive?.issue ?? '质量问题待修复'}`);
  }

  if (event.type === 'manual_intervention_required') {
    setters.setRunning(false);
    setters.setPaused(true);
    setters.setLatestResult(event.reason ?? '发现不可自动修复的质量阻断，需要人工处理。');
  }

  if (event.type === 'chapter_progress_updated') {
    setters.setLatestResult(
      `正文进度已更新：${event.chapters?.filter((item) => item.status === 'completed').length ?? 0}/${event.chapters?.length ?? 0} 章`,
    );
  }

  if (event.type === 'node_completed') setters.setLatestResult(formatResult(event.result));
  if (event.type === 'node_failed') setters.setLatestResult(event.error ?? '节点失败');
}

function syncStageSelection(nodeId: string, setters: EventSetters) {
  setters.setWorkspacePhase('running');
  setters.setSelectedId(nodeId);
  setters.setSelectedInspectorTarget({ kind: 'stage', id: nodeId });
}
