import type { RunEvent } from '../contracts';

const terminalTypes = new Set([
  'approval_required',
  'node_completed',
  'node_failed',
  'run_blocked',
  'run_error',
  'run_failed',
  'run_paused',
  'stage_checkpoint_ready',
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
    && (!event.node_id || event.node_id === 'info')
  ));
  return !terminal;
}

export function infoStageLoadingCopy(events: RunEvent[]) {
  const latest = events.find((event) => (
    referenceTypes.has(event.type)
    || (event.node_id === 'info' && (event.type === 'memory_context_loaded' || event.type === 'node_started'))
    || event.type === 'run_started'
  ));
  if (!latest) return { detail: '马上开始', title: '正在建立创作任务' };
  if (latest.type === 'reference_collection_started') return { detail: '正在从选定来源整理可用参考', title: '正在收集参考资料' };
  if (latest.type === 'reference_source_found') return { detail: String(latest.title || latest.section || '已收到一条可用来源'), title: '参考来源已接入' };
  if (latest.type === 'reference_understanding_completed' || latest.type === 'reference_context_merged') return { detail: '正在提炼结构、题材边界与风险', title: '正在理解参考内容' };
  if (latest.type === 'reference_context_injected') return { detail: '参考摘要已进入小说信息上下文', title: '参考上下文已就绪' };
  if (latest.type === 'memory_context_loaded') return { detail: '正在合并项目记忆与创作配置', title: '正在装配创作上下文' };
  if (latest.type === 'node_started') return { detail: '等待创作立项内容通过结构检查', title: '正在生成小说信息推荐' };
  return { detail: '运行已建立，等待信息推荐阶段开始', title: '正在准备小说信息' };
}

export function infoStageLoadingMilestones(events: RunEvent[]) {
  const runStarted = events.some((event) => event.type === 'run_started' || event.type === 'run_resumed');
  const generationStarted = events.some((event) => event.type === 'node_started' && event.node_id === 'info');
  const referencesReady = generationStarted || events.some((event) => event.type === 'reference_context_injected');
  return [
    { complete: runStarted, label: '创作配置已提交' },
    { complete: referencesReady, label: '参考上下文已装配' },
    { complete: false, current: generationStarted, label: '生成小说信息' },
  ];
}
