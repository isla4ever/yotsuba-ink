import { MarkerType, type Edge, type Node } from '@xyflow/react';
import { CrosscuttingNode, StageCompactNode } from './StageCompactNode';
import type { CanvasLayout, RunEvent, WorkflowDefinition } from '../contracts';
import { latestNodeStatus } from './cockpitRuntime';
import { stageLabelForUi } from '../lib/display';
import { stageArtifactLabel, stageConfigurationReadiness } from '../lib/planningReadiness';

export const pipelineNodeTypes = { stageCompact: StageCompactNode, crosscutting: CrosscuttingNode };

const crosscuttingTargetIds = ['summary', 'outline', 'detail', 'text'];
export type PipelineLayoutVariant = 'planning' | 'cockpit-vertical';

export function isCanvasNodeActivationKey(key: string) {
  return key === 'Enter' || key === ' ';
}

export function isCanvasViewportInteractive(lockedViewport: boolean, layoutLocked: boolean) {
  return !lockedViewport && !layoutLocked;
}

export function mergeLayoutNodes(
  workflow: WorkflowDefinition,
  selectedId: string,
  events: RunEvent[],
  currentNodes: Node[],
  showCrosscutting = workflow.canvas_layout?.crosscutting_visible !== false,
  layoutVariant: PipelineLayoutVariant = 'planning',
  runtimeLayersEnabled = true,
): Node[] {
  if (layoutVariant === 'cockpit-vertical') {
    return buildNodes(workflow, selectedId, events, showCrosscutting, layoutVariant, runtimeLayersEnabled);
  }
  const currentById = new Map(currentNodes.map((node) => [node.id, node]));
  const next = buildNodes(workflow, selectedId, events, showCrosscutting, layoutVariant, runtimeLayersEnabled);
  return next.map((node) => {
    const current = currentById.get(node.id);
    return current ? { ...node, position: current.position ?? node.position } : node;
  });
}

export function layoutFromNodes(workflow: WorkflowDefinition, nextNodes: Node[]) {
  const current = Object.fromEntries(
    nextNodes
      .filter((node) => node.position && typeof node.position.x === 'number' && typeof node.position.y === 'number')
      .map((node) => [node.id, { x: Math.round(node.position.x), y: Math.round(node.position.y) }]),
  );
  const required = [
    ...workflow.nodes.map((stage) => stage.id),
    ...(workflow.canvas_layout?.crosscutting_visible === false ? [] : ['wiki-layer', 'quality-layer']),
  ];
  for (const [index, id] of required.entries()) {
    if (!current[id]) current[id] = workflow.canvas_layout?.nodes?.[id] ?? defaultPosition(id, index);
  }
  return current;
}

export function buildNodes(
  workflow: WorkflowDefinition,
  selectedId: string,
  events: RunEvent[],
  showCrosscutting = workflow.canvas_layout?.crosscutting_visible !== false,
  layoutVariant: PipelineLayoutVariant = 'planning',
  runtimeLayersEnabled = true,
): Node[] {
  const layout = workflow.canvas_layout?.nodes ?? {};
  const useCockpitLayout = layoutVariant === 'cockpit-vertical';
  const useDefaultLayout = useCockpitLayout || needsDefaultCanvasLayout(workflow);
  const wikiSubtitle = runtimeLayersEnabled ? useCockpitLayout ? '读写约束' : '读取 / 写回 / 冲突处理' : '启动后可用';
  const qualitySubtitle = runtimeLayersEnabled ? useCockpitLayout ? '评分复检' : '评分 / 重试 / 版本评审' : '启动后可用';
  const stageNodes = workflow.nodes.map((stage, index) => ({
    id: stage.id,
    type: 'stageCompact',
    position: useCockpitLayout ? cockpitPosition(stage.id, index) : useDefaultLayout ? defaultPosition(stage.id, index) : layout[stage.id] ?? defaultPosition(stage.id, index),
    ariaLabel: stageNodeAriaLabel(stage, index, selectedId === stage.id, useCockpitLayout, runtimeLayersEnabled),
    ariaRole: 'button' as const,
    focusable: true,
    selectable: true,
    selected: selectedId === stage.id,
    data: {
      stage,
      index,
      selected: selectedId === stage.id,
      status: statusFor(stage.id, events),
      events,
      presentation: useCockpitLayout ? 'runtime' : 'planning',
      runtime: latestNodeStatus(events, stage.id),
    },
  }));
  if (!showCrosscutting) return stageNodes;
  return [
    ...stageNodes,
    {
      id: 'wiki-layer',
      type: 'crosscutting',
      position: useCockpitLayout ? { x: 78, y: 350 } : useDefaultLayout ? { x: 324, y: -96 } : layout['wiki-layer'] ?? { x: 324, y: -96 },
      ariaLabel: runtimeLayersEnabled ? 'Wiki 事实层，打开事实读写详情' : 'Wiki 事实层，启动创作后可用',
      ariaRole: runtimeLayersEnabled ? 'button' as const : 'group' as const,
      data: { compact: useCockpitLayout, disabled: !runtimeLayersEnabled, kind: 'wiki', title: useCockpitLayout ? 'Wiki约束' : 'Wiki 自动约束', subtitle: wikiSubtitle, selected: runtimeLayersEnabled && selectedId === 'wiki-layer' },
      draggable: runtimeLayersEnabled,
      focusable: runtimeLayersEnabled,
      selectable: runtimeLayersEnabled,
    },
    {
      id: 'quality-layer',
      type: 'crosscutting',
      position: useCockpitLayout ? { x: 414, y: 350 } : useDefaultLayout ? { x: 708, y: 452 } : layout['quality-layer'] ?? { x: 708, y: 452 },
      ariaLabel: runtimeLayersEnabled ? '质量监控，打开质量检查详情' : '质量监控，启动创作后可用',
      ariaRole: runtimeLayersEnabled ? 'button' as const : 'group' as const,
      data: { compact: useCockpitLayout, disabled: !runtimeLayersEnabled, kind: 'quality', title: '质量检查', subtitle: qualitySubtitle, selected: runtimeLayersEnabled && selectedId === 'quality-layer' },
      draggable: runtimeLayersEnabled,
      focusable: runtimeLayersEnabled,
      selectable: runtimeLayersEnabled,
    },
  ];
}

function stageNodeAriaLabel(stage: WorkflowDefinition['nodes'][number], index: number, selected: boolean, cockpit: boolean, runtimeEnabled: boolean) {
  const readiness = stageConfigurationReadiness(stage);
  const state = cockpit
    ? runtimeEnabled ? '打开只读阶段快照' : '打开阶段设置'
    : readiness.ready ? '配置就绪' : `待补 ${readiness.missingLabels.length} 项`;
  const selection = selected ? '，当前选中' : '';
  return `第 ${index + 1} 阶段，${stageLabelForUi(stage)}，产物为${stageArtifactLabel(stage)}，${state}${selection}`;
}

function needsDefaultCanvasLayout(workflow: WorkflowDefinition) {
  const layout = workflow.canvas_layout?.nodes;
  if (!layout) return false;
  const stagePositions = workflow.nodes.map((stage) => layout[stage.id]).filter(Boolean);
  if (stagePositions.length < 4) return false;
  const xSpread = Math.max(...stagePositions.map((item) => item.x)) - Math.min(...stagePositions.map((item) => item.x));
  const ySpread = Math.max(...stagePositions.map((item) => item.y)) - Math.min(...stagePositions.map((item) => item.y));
  const wiki = layout['wiki-layer'];
  const quality = layout['quality-layer'];
  const crosscuttingSameSide = Boolean(wiki && quality && Math.abs(wiki.y - quality.y) < 100);
  const crosscuttingSideMounted = Boolean(
    wiki && quality && Math.abs(wiki.y - quality.y) < 180 && Math.abs(wiki.x - quality.x) > 260,
  );
  const tooWideForCurrentBaseline = Math.max(...stagePositions.map((item) => item.x)) > 1320;
  return (xSpread < 120 && ySpread > 360) || crosscuttingSameSide || crosscuttingSideMounted || tooWideForCurrentBaseline;
}

export function buildEdges(
  workflow: WorkflowDefinition,
  events: RunEvent[],
  selectedId: string,
  showCrosscutting = workflow.canvas_layout?.crosscutting_visible !== false,
  layoutVariant: PipelineLayoutVariant = 'planning',
  runtimeLayersEnabled = true,
): Edge[] {
  const cockpit = layoutVariant === 'cockpit-vertical';
  const mainEdges = workflow.edges.map((edge) => ({
    ...edge,
    animated: latestNodeStatus(events, edge.target).status === 'running',
    className: 'pipeline-edge',
    sourceHandle: cockpit ? 'bottom-source' : 'right',
    targetHandle: cockpit ? 'top' : 'left',
    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--edge)', width: 14, height: 14 },
    type: 'smoothstep' as const,
  }));
  if (!showCrosscutting) return mainEdges;
  const wikiActive = runtimeLayersEnabled && (selectedId === 'wiki-layer' || events.some((event) => event.type === 'evidence.proposed' || event.type === 'writeback.committed'));
  const qualityActive = runtimeLayersEnabled && (selectedId === 'quality-layer' || events.some((event) => event.type === 'review.started' || event.type === 'review.completed'));
  const disabledClass = runtimeLayersEnabled ? '' : ' disabled';
  const crosscutting = crosscuttingTargetIds.flatMap((nodeId) => [
    {
      id: `wiki-${nodeId}`,
      source: 'wiki-layer',
      target: nodeId,
      sourceHandle: cockpit ? 'right' : 'bottom',
      targetHandle: cockpit ? 'left' : 'top',
      animated: wikiActive,
      className: `crosscutting-edge wiki-edge${wikiActive ? ' active' : ''}${runtimeLayersEnabled && selectedId === 'wiki-layer' ? ' selected' : ''}${disabledClass}`,
      type: cockpit ? 'straight' as const : 'smoothstep' as const,
    },
    {
      id: `quality-${nodeId}`,
      source: 'quality-layer',
      target: nodeId,
      sourceHandle: cockpit ? 'left' : 'top',
      targetHandle: cockpit ? 'right-target' : 'bottom',
      animated: qualityActive,
      className: `crosscutting-edge quality-edge${qualityActive ? ' active' : ''}${runtimeLayersEnabled && selectedId === 'quality-layer' ? ' selected' : ''}${disabledClass}`,
      type: cockpit ? 'straight' as const : 'smoothstep' as const,
    },
  ]);
  return [...mainEdges, ...crosscutting];
}

export function createCanvasLayout(
  workflow: WorkflowDefinition,
  nodes: Node[],
  viewport: CanvasLayout['viewport'],
  locked = workflow.canvas_layout?.locked ?? false,
): CanvasLayout {
  return {
    nodes: layoutFromNodes(workflow, nodes),
    viewport,
    crosscutting_visible: workflow.canvas_layout?.crosscutting_visible ?? true,
    locked,
  };
}

function defaultPosition(stageId: string, index: number) {
  const map: Record<string, { x: number; y: number }> = {
    info: { x: -12, y: 178 },
    summary: { x: 176, y: 178 },
    outline: { x: 364, y: 178 },
    detail: { x: 552, y: 178 },
    text: { x: 740, y: 178 },
    cover: { x: 928, y: 178 },
    export: { x: 1116, y: 178 },
  };
  return map[stageId] ?? { x: -12 + index * 188, y: 178 };
}

function cockpitPosition(stageId: string, index: number) {
  const map: Record<string, { x: number; y: number }> = {
    info: { x: 204, y: 42 },
    summary: { x: 204, y: 166 },
    outline: { x: 204, y: 290 },
    detail: { x: 204, y: 414 },
    text: { x: 204, y: 538 },
    cover: { x: 204, y: 662 },
    export: { x: 204, y: 786 },
  };
  return map[stageId] ?? { x: 204, y: 42 + index * 124 };
}

function statusFor(stageId: string, events: RunEvent[]) {
  return latestNodeStatus(events, stageId).status;
}
