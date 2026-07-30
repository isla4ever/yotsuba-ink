import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { runEventEntryLabel } from '../lib/runEventLabels';
import { stageUsageElapsedMs, stageUsageFromEvents } from '../lib/stageUsage';

export type NodeRunStatus = 'idle' | 'running' | 'done' | 'failed';

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
  const latestNodeEvent = events.find((event) => event.node_id === stageId && isNodeStatusEvent(event));
  const started = events.find((event) => event.node_id === stageId && event.type === 'node_started');
  const checkpoint = events.find((event) => event.node_id === stageId && event.type === 'stage_checkpoint_ready');
  const completed = events.find((event) => event.node_id === stageId && event.type === 'node_completed');
  const usageElapsedMs = stageUsageElapsedMs(stageUsageFromEvents(events, stageId));
  const completedMs = Number(checkpoint?.elapsed_ms ?? completed?.elapsed_ms ?? usageElapsedMs ?? 0);
  if (!latestNodeEvent) {
    return { status: 'idle', startKey: '', startedAtMs: null, completedSeconds: null };
  }
  if (latestNodeEvent.type === 'node_failed' || latestNodeEvent.type === 'run_error') {
    return { status: 'failed', startKey: '', startedAtMs: eventTimeMs(started), completedSeconds: null };
  }
  if (
    latestNodeEvent.type === 'node_completed'
    || latestNodeEvent.type === 'stage_artifact_confirmed'
    || latestNodeEvent.type === 'artifact_approved'
  ) {
    return {
      status: 'done',
      startKey: '',
      startedAtMs: eventTimeMs(started),
      completedSeconds: Number.isFinite(completedMs) && completedMs > 0 ? Math.max(1, Math.round(completedMs / 1000)) : null,
    };
  }
  if (latestNodeEvent.type === 'node_started') {
    if (latestNodeEvent.phase === 'finalizing') {
      return {
        status: 'done',
        startKey: '',
        startedAtMs: eventTimeMs(started),
        completedSeconds: null,
      };
    }
    return {
      status: 'running',
      startKey: started ? `${started.run_id}-${started.node_id}-${started.label ?? ''}` : '',
      startedAtMs: eventTimeMs(started),
      completedSeconds: null,
    };
  }
  return { status: 'idle', startKey: '', startedAtMs: null, completedSeconds: null };
}

function isNodeStatusEvent(event: RunEvent) {
  return event.type.startsWith('node_')
    || event.type === 'run_error'
    || event.type === 'stage_artifact_confirmed'
    || event.type === 'artifact_approved';
}

export function activeCockpitStageId(events: RunEvent[], selectedId: string, workflow: WorkflowDefinition) {
  const stageIds = workflow.nodes.map((stage) => stage.id);
  const stageIdSet = new Set(stageIds);
  const runningEvent = events.find((event) => event.node_id && stageIdSet.has(event.node_id) && latestNodeStatus(events, event.node_id).status === 'running');
  if (runningEvent?.node_id) return runningEvent.node_id;
  const latestStageEvent = events.find((event) => event.node_id && stageIdSet.has(event.node_id));
  if (!latestStageEvent?.node_id) return selectedId;
  return latestStageEvent.node_id;
}

export function displayRunLogEvents(events: RunEvent[], stage: WorkflowStage): DisplayRunLogItem[] {
  const stageEvents = events.filter((event) => event.node_id === stage.id);
  const runtime = latestNodeStatus(events, stage.id);
  const main = mainLogItem(stageEvents, stage, runtime.status);
  const lanes = agentLaneItems(stageEvents);
  if (main || lanes.length) return [main, ...lanes].filter(Boolean).slice(0, 5) as DisplayRunLogItem[];
  return [];
}

function mainLogItem(stageEvents: RunEvent[], stage: WorkflowStage, status: NodeRunStatus): DisplayRunLogItem | null {
  const done = status === 'done';
  if (stage.type === 'chapter_text') {
    const chapterEvent = stageEvents.find((event) => event.type === 'chapter_delta' || event.type === 'chapter_started');
    const contextEvent = stageEvents.find((event) => event.type === 'chapter_context_built');
    const progressEvent = stageEvents.find((event) => event.type === 'chapter_progress_updated');
    const chapter = chapterEvent?.chapter ?? contextEvent?.chapter ?? '当前章节';
    const deltas = stageEvents
      .filter((event) => event.type === 'chapter_delta' && event.chapter === chapter && event.delta)
      .slice(0, 12)
      .reverse()
      .map((event) => event.delta)
      .join('');
    if (deltas) {
      return { agent: 'main', key: 'main-content', title: done ? `${chapter} 正文已完成` : `${chapter} 正文写入中`, detail: deltas, status: done ? 'done' : 'running', tone: done ? 'done' : 'content' };
    } else if (contextEvent) {
      return {
        agent: 'main',
        key: 'main-content',
        title: `${chapter} 正文生成准备`,
        detail: '本章细纲与前情已备齐，正文即将开始生成。',
        status: 'running',
        tone: 'running',
      };
    } else if (progressEvent?.chapters?.length) {
      const total = progressEvent.chapters.length;
      const done = progressEvent.chapters.filter((item) => item.status === 'completed').length;
      return {
        agent: 'main',
        key: 'main-content',
        title: '正文队列已建立',
        detail: `${done}/${total} 章完成，正在准备下一章的写作上下文。`,
        status: 'running',
        tone: 'content',
      };
    }
    return null;
  }
  const latestAsset = stageEvents.find((event) => event.type === 'asset_progress_updated');
  const deltas = stageEvents
    .filter((event) => event.type === 'artifact_stream_delta' && event.delta)
    .slice(0, 5)
    .reverse();
  if (deltas.length) {
    const latest = deltas[deltas.length - 1];
    return {
      agent: 'main',
      key: 'main-content',
      title: done ? `${stage.label}产物已完成` : `${latest.section || stage.label} · 生成中`,
      detail: deltas.map((event) => `${event.section ? `${event.section}：` : ''}${event.delta}`).join('\n'),
      status: done ? 'done' : 'running',
      tone: done ? 'done' : 'content',
    };
  }
  if (latestAsset) {
    return {
      agent: 'main',
      key: 'main-content',
      title: done ? `${stage.label}已完成` : `${latestAsset.section || stage.label} · 处理中`,
      detail: latestAsset.message || '素材处理进行中。',
      progress: assetProgressFraction(latestAsset, done),
      status: done ? 'done' : 'running',
      tone: done ? 'done' : 'content',
    };
  }
  if (stageEvents.some((event) => event.type === 'node_started')) {
    return {
      agent: 'main',
      key: 'main-content',
      title: done ? `${stage.label}已完成` : `${stage.label} · 执行中`,
      detail: done ? '本阶段内容已生成完成。' : '已读取前面阶段的成果，正在生成本阶段内容。',
      status: done ? 'done' : 'running',
      tone: done ? 'done' : 'running',
    };
  }
  return null;
}

function agentLaneItems(stageEvents: RunEvent[]): DisplayRunLogItem[] {
  const items: DisplayRunLogItem[] = [];
  const memoryWrite = stageEvents.find((event) => event.type === 'memory_writeback_completed');
  const memoryRead = stageEvents.find((event) => event.type === 'memory_context_loaded');
  if (memoryRead || memoryWrite) {
    items.push({
      agent: 'wiki',
      key: 'agent-wiki',
      title: 'Wiki 事实写回',
      detail: memoryWrite ? '事实层与连续性上下文已写回。' : '人物状态、世界观硬设定与未回收伏笔已注入。',
      status: memoryWrite ? 'done' : 'running',
      tone: 'agent',
    });
  }
  const qualityDone = stageEvents.find((event) => event.type === 'quality_check_completed');
  const qualityStarted = stageEvents.find((event) => event.type === 'quality_check_started');
  if (qualityStarted || qualityDone) {
    const score = qualityDone?.quality_report?.score ?? qualityDone?.quality?.score;
    items.push({
      agent: 'quality',
      key: 'agent-quality',
      title: '质量检查',
      detail: qualityDone ? (score ? `检查完成 · Q ${score.toFixed(2)}` : '本阶段检查完成。') : '正在检查连续性、人物动机与伏笔落点。',
      status: qualityDone ? 'done' : 'running',
      tone: 'agent',
    });
  }
  const asset = stageEvents.find((event) => event.type === 'asset_progress_updated');
  if (asset) {
    const nodeCompleted = stageEvents.some((event) => event.type === 'node_completed');
    const progress = assetProgressFraction(asset, nodeCompleted);
    const completed = nodeCompleted || progress === 1;
    items.push({
      agent: 'asset',
      key: 'agent-asset',
      title: '素材处理',
      detail: asset.message || `${asset.section ?? '素材'}处理进行中。`,
      progress,
      status: completed ? 'done' : 'running',
      tone: 'agent',
    });
  }
  const provider = providerRetryItem(stageEvents);
  if (provider) items.push(provider);
  const checkpoint = stageEvents.find((event) => event.type === 'stage_checkpoint_ready' || event.type === 'stage_summary_ready');
  if (checkpoint) {
    items.push({
      agent: 'settlement',
      key: 'agent-settlement',
      title: '阶段结算',
      detail: checkpoint.message || (checkpoint.next_step ? `准备进入 ${checkpoint.next_step}` : '阶段完成，等待下一步。'),
      status: 'done',
      tone: 'milestone',
    });
  }
  return items;
}

/**
 * Phase 12 D9: provider retry/fallback events (10.4a) as a writer-language
 * run-log lane — shown while the newest provider signal is a retry/fallback,
 * cleared once a newer attempt succeeds.
 */
function providerRetryItem(stageEvents: RunEvent[]): DisplayRunLogItem | null {
  const latest = stageEvents.find((event) => event.type.startsWith('provider_'));
  if (!latest) return null;
  if (latest.type === 'provider_attempt_succeeded') return null;
  if (latest.type === 'provider_attempt_started' && Number(latest.attempt ?? 1) <= 1) return null;
  const detail = latest.type === 'provider_fallback_scheduled'
    ? '主服务暂时不可用，已自动切换到备用服务继续生成。'
    : latest.type === 'provider_fallback_blocked'
      ? '多次尝试仍未成功，请检查 AI 服务配置后继续。'
      : latest.type === 'provider_attempt_failed'
        ? '上次调用未成功，正在自动重试。'
        : '正在通过备用线路重新调用 AI 服务。';
  return {
    agent: 'provider',
    key: 'agent-provider',
    title: runEventEntryLabel(latest),
    detail,
    status: latest.type === 'provider_fallback_blocked' ? 'idle' : 'running',
    tone: 'agent',
  };
}

/**
 * Phase 12 D2: progress is derived only from real backend counts
 * (`ready_count`/`failed_count`/`total` on asset_progress_updated). Without
 * counts the result is undefined so the UI stays indeterminate instead of
 * showing a fabricated percentage.
 */
function assetProgressFraction(event: RunEvent, completed: boolean): number | undefined {
  if (completed) return 1;
  const total = Number(event.total);
  if (!Number.isFinite(total) || total <= 0) return undefined;
  const processed = (Number(event.ready_count) || 0) + (Number(event.failed_count) || 0);
  return Math.max(0, Math.min(1, processed / total));
}

export function runtimeElapsedSeconds(runtime: NodeRuntimeState, now = Date.now()) {
  if (runtime.completedSeconds) return runtime.completedSeconds;
  if (runtime.status !== 'running' || !runtime.startedAtMs) return null;
  return Math.max(1, Math.round((now - runtime.startedAtMs) / 1000));
}

function eventTimeMs(event?: RunEvent) {
  if (!event?.created_at) return null;
  const value = Date.parse(event.created_at);
  return Number.isFinite(value) ? value : null;
}
