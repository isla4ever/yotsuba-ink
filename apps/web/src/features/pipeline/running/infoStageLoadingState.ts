import type { RunEvent } from '../contracts';

const terminalTypes = new Set([
  'artifact.candidate_ready',
  'artifact.committed',
  'node.completed',
  'node.failed',
  'run.failed',
  'decision.required',
]);

const referenceTypes = new Set([
  'reference_collection_started',
  'reference_source_found',
  'reference_understanding_completed',
  'reference_context_merged',
  'reference_context_injected',
]);

export function infoStageLoadingVisible(activeRunId: string, events: RunEvent[]) {
  if (!activeRunId) return false;
  const terminal = events.some((event) => (
    terminalTypes.has(event.type)
    && (!event.stage_id || event.stage_id === 'info')
  ));
  return !terminal;
}

export function infoStageLoadingCopy(events: RunEvent[]) {
  const latest = events.find((event) => (
    referenceTypes.has(event.type)
    || (event.stage_id === 'info' && (event.type === 'evidence.proposed' || event.type === 'node.started'))
    || event.type === 'run.started'
  ));
  if (!latest) return { detail: '马上开始', title: '正在建立创作任务' };
  if (latest.type === 'reference_collection_started') return { detail: '正在从选定来源整理可用参考', title: '正在收集参考资料' };
  if (latest.type === 'reference_source_found') return { detail: payloadText(latest, 'title') || payloadText(latest, 'section') || '已收到一条可用来源', title: '参考来源已接入' };
  if (latest.type === 'reference_understanding_completed' || latest.type === 'reference_context_merged') return { detail: '正在提炼结构、题材边界与风险', title: '正在理解参考内容' };
  if (latest.type === 'reference_context_injected') return { detail: '参考摘要已进入创作立项上下文', title: '参考上下文已就绪' };
  if (latest.type === 'evidence.proposed') return { detail: '正在合并已选资料与创作配置', title: '正在装配规划上下文' };
  if (latest.type === 'node.started') return { detail: '等待创作立项内容通过结构检查', title: '正在生成创作立项' };
  return { detail: '运行已建立，等待创作立项阶段开始', title: '正在准备创作立项' };
}

function payloadText(event: RunEvent, key: string) {
  const value = event.payload?.[key];
  return typeof value === 'string' ? value : '';
}

export function infoStageLoadingMilestones(events: RunEvent[]) {
  const runStarted = events.some((event) => event.type === 'run.started');
  const generationStarted = events.some((event) => event.type === 'node.started' && event.stage_id === 'info');
  const referencesReady = generationStarted || events.some((event) => event.type === 'reference_context_injected');
  return [
    { complete: runStarted, label: '创作配置已提交' },
    { complete: referencesReady, label: '参考上下文已装配' },
    { complete: false, current: generationStarted, label: '生成创作立项' },
  ];
}
