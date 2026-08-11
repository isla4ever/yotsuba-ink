import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';

export type NodeRunStatus = 'idle' | 'running' | 'awaiting' | 'done' | 'failed';

export type NodeRuntimeState = {
  status: NodeRunStatus;
  startKey: string;
  startedAtMs: number | null;
  completedSeconds: number | null;
};

export type DisplayRunLogItem = {
  agent?: 'main' | 'wiki' | 'quality' | 'asset' | 'settlement' | 'provider';
  key: string;
  title: string;
  detail: string;
  progress?: number;
  status?: 'idle' | 'running' | 'done';
  tone?: 'content' | 'support' | 'done' | 'running' | 'milestone' | 'agent';
};

export function latestNodeStatus(events: RunEvent[], stageId: string): NodeRuntimeState {
  const stageEvents = events.filter((event) => eventStageId(event) === stageId);
  const latest = stageEvents.find(isLifecycleEvent);
  const started = stageEvents.find((event) => event.type === 'node.started');
  if (!latest) return { status: 'idle', startKey: '', startedAtMs: null, completedSeconds: null };
  if (latest.type === 'node.failed' || latest.type === 'run.failed') {
    return { status: 'failed', startKey: '', startedAtMs: eventTimeMs(started), completedSeconds: null };
  }
  if (latest.type === 'decision.required') {
    return { status: 'awaiting', startKey: '', startedAtMs: eventTimeMs(started), completedSeconds: null };
  }
  if (stageCompletedBy(latest)) {
    return { status: 'done', startKey: '', startedAtMs: eventTimeMs(started), completedSeconds: elapsedSeconds(started, latest) };
  }
  return {
    status: 'running',
    startKey: started ? `${started.run_id}-${started.event_id}` : '',
    startedAtMs: eventTimeMs(started),
    completedSeconds: null,
  };
}

export function activeCockpitStageId(events: RunEvent[], selectedId: string, workflow: WorkflowDefinition) {
  const stageIds = new Set(workflow.nodes.map((stage) => stage.id));
  const running = events.find((event) => stageIds.has(eventStageId(event)) && latestNodeStatus(events, eventStageId(event)).status === 'running');
  if (running) return eventStageId(running);
  const latest = events.find((event) => stageIds.has(eventStageId(event)));
  return latest ? eventStageId(latest) : selectedId;
}

export function displayRunLogEvents(events: RunEvent[], stage: WorkflowStage): DisplayRunLogItem[] {
  const stageEvents = events.filter((event) => eventStageId(event) === stage.id);
  const items: DisplayRunLogItem[] = [];
  const latestNode = stageEvents.find((event) => event.type.startsWith('node.'));
  if (latestNode) {
    const failed = latestNode.type === 'node.failed';
    const done = latestNode.type === 'node.completed';
    items.push({
      agent: 'main',
      key: `node-${latestNode.event_id}`,
      title: nodeTitle(latestNode.node_id),
      detail: failed ? failureText(latestNode) : done ? '节点已完成，状态由 LangGraph 检查点持久化。' : 'LangGraph 正在执行当前节点。',
      status: failed || done ? 'done' : 'running',
      tone: failed ? 'support' : done ? 'done' : 'running',
    });
  }
  const review = stageEvents.find((event) => event.type === 'review.completed' || event.type === 'review.unavailable' || event.type === 'review.started');
  if (review) {
    const role = payloadText(review, 'role') || '审稿角色';
    const findings = Array.isArray(review.payload?.findings) ? review.payload.findings.length : 0;
    items.push({
      agent: 'quality',
      key: `review-${review.event_id}`,
      title: review.type === 'review.started' ? `${role}审稿中` : `${role}审稿结果`,
      detail: review.type === 'review.unavailable' ? '该审稿角色不可用，Graph 将按质量门策略请求人工决定。' : `${findings} 个结构化发现。`,
      status: review.type === 'review.started' ? 'running' : 'done',
      tone: 'agent',
    });
  }
  const writeback = stageEvents.find((event) => event.type.startsWith('writeback.'));
  if (writeback) {
    items.push({
      agent: 'wiki',
      key: `writeback-${writeback.event_id}`,
      title: writeback.type === 'writeback.committed' ? '事实写回已提交' : writeback.type === 'writeback.failed' ? '事实写回失败' : '事实写回已排队',
      detail: payloadText(writeback, 'transaction_id') || failureText(writeback) || '等待事务回执。',
      status: writeback.type === 'writeback.queued' ? 'running' : 'done',
      tone: 'agent',
    });
  }
  const checkpoint = stageEvents.find((event) => event.type === 'checkpoint.saved');
  if (checkpoint) {
    items.push({
      agent: 'settlement',
      key: `checkpoint-${checkpoint.event_id}`,
      title: '检查点已保存',
      detail: checkpoint.checkpoint_id,
      status: 'done',
      tone: 'milestone',
    });
  }
  return items.slice(0, 5);
}

export function runtimeElapsedSeconds(runtime: NodeRuntimeState, now = Date.now()) {
  if (runtime.completedSeconds) return runtime.completedSeconds;
  if (runtime.status !== 'running' || !runtime.startedAtMs) return null;
  return Math.max(1, Math.round((now - runtime.startedAtMs) / 1000));
}

function isLifecycleEvent(event: RunEvent) {
  return event.type.startsWith('node.')
    || event.type === 'artifact.candidate_ready'
    || event.type === 'artifact.committed'
    || event.type === 'decision.required'
    || event.type === 'decision.resolved'
    || event.type === 'run.failed';
}

function eventStageId(event: RunEvent) {
  return event.stage_id || event.node_id.split('.')[0] || '';
}

function stageCompletedBy(event: RunEvent) {
  if (event.type === 'artifact.committed' && event.stage_id !== 'text') return true;
  return event.type === 'node.completed' && (event.node_id.endsWith('.checkpoint_stage') || event.node_id === 'text.finish_chapters');
}

function eventTimeMs(event?: RunEvent) {
  if (!event) return null;
  const value = Date.parse(event.occurred_at);
  return Number.isFinite(value) ? value : null;
}

function elapsedSeconds(started: RunEvent | undefined, completed: RunEvent) {
  const start = eventTimeMs(started);
  const end = eventTimeMs(completed);
  if (start == null || end == null || end < start) return null;
  return Math.max(1, Math.round((end - start) / 1000));
}

function nodeTitle(nodeId: string) {
  const parts = nodeId.split('.');
  return parts[parts.length - 1]?.replace(/_/g, ' ') || 'Graph 节点';
}

function payloadText(event: RunEvent, key: string) {
  const value = event.payload?.[key];
  return typeof value === 'string' ? value : '';
}

function failureText(event: RunEvent) {
  return payloadText(event, 'message') || payloadText(event, 'code');
}
