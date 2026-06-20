import type { Edge, Node } from '@xyflow/react';
import { CrosscuttingNode, StageCompactNode } from './StageCompactNode';
import type { CanvasLayout, QualityEvent, RunEvent, WorkflowDefinition } from '../contracts';

export const pipelineNodeTypes = { stageCompact: StageCompactNode, crosscutting: CrosscuttingNode };

const crosscuttingTargetIds = ['summary', 'outline', 'detail', 'text'];

export function createQualityMap(events: RunEvent[]) {
  const map = new Map<string, QualityEvent>();
  events.forEach((event) => {
    if (event.type === 'quality_check_completed' && event.node_id && event.quality) {
      map.set(event.node_id, event.quality);
    }
  });
  return map;
}

export function mergeLayoutNodes(
  workflow: WorkflowDefinition,
  selectedId: string,
  events: RunEvent[],
  latestQuality: Map<string, QualityEvent>,
  currentNodes: Node[],
): Node[] {
  const currentById = new Map(currentNodes.map((node) => [node.id, node]));
  const next = buildNodes(workflow, selectedId, events, latestQuality);
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
  latestQuality: Map<string, QualityEvent>,
): Node[] {
  const layout = workflow.canvas_layout?.nodes ?? {};
  const stageNodes = workflow.nodes.map((stage, index) => ({
    id: stage.id,
    type: 'stageCompact',
    position: layout[stage.id] ?? defaultPosition(stage.id, index),
    data: {
      stage,
      index,
      selected: selectedId === stage.id,
      status: statusFor(stage.id, events),
      quality: latestQuality.get(stage.id),
      events,
    },
  }));
  if (workflow.canvas_layout?.crosscutting_visible === false) return stageNodes;
  return [
    ...stageNodes,
    {
      id: 'wiki-layer',
      type: 'crosscutting',
      position: layout['wiki-layer'] ?? { x: 276, y: 302 },
      data: { kind: 'wiki', title: 'Wiki 自动约束', subtitle: '读取 / 写回 / 冲突处理', selected: selectedId === 'wiki-layer' },
      draggable: true,
    },
    {
      id: 'quality-layer',
      type: 'crosscutting',
      position: layout['quality-layer'] ?? { x: 694, y: 302 },
      data: { kind: 'quality', title: '质量阀门', subtitle: '评分 / 重试 / 版本评审', selected: selectedId === 'quality-layer' },
      draggable: true,
    },
  ];
}

export function buildEdges(workflow: WorkflowDefinition, events: RunEvent[], selectedId: string): Edge[] {
  const mainEdges = workflow.edges.map((edge) => ({
    ...edge,
    animated: events.some((event) => event.type === 'node_started' && event.node_id === edge.target),
    className: 'pipeline-edge',
    sourceHandle: 'bottom',
    targetHandle: 'top',
    type: 'smoothstep' as const,
  }));
  if (workflow.canvas_layout?.crosscutting_visible === false) return mainEdges;
  const crosscutting = crosscuttingTargetIds.flatMap((nodeId) => [
    {
      id: `wiki-${nodeId}`,
      source: 'wiki-layer',
      target: nodeId,
      sourceHandle: 'right',
      targetHandle: 'left',
      animated: true,
      className: `crosscutting-edge wiki-edge${selectedId === 'wiki-layer' ? ' selected' : ''}`,
      type: 'smoothstep' as const,
    },
    {
      id: `quality-${nodeId}`,
      source: 'quality-layer',
      target: nodeId,
      sourceHandle: 'left',
      targetHandle: 'right-target',
      animated: true,
      className: `crosscutting-edge quality-edge${selectedId === 'quality-layer' ? ' selected' : ''}`,
      type: 'smoothstep' as const,
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
    info: { x: 420, y: 20 },
    summary: { x: 420, y: 160 },
    outline: { x: 420, y: 300 },
    detail: { x: 420, y: 440 },
    text: { x: 420, y: 580 },
    cover: { x: 420, y: 720 },
    export: { x: 420, y: 860 },
  };
  return map[stageId] ?? { x: 420, y: index * 140 };
}

function statusFor(stageId: string, events: RunEvent[]) {
  const latest = events.find((event) => event.node_id === stageId && event.type.startsWith('node_'));
  if (!latest) return 'idle';
  if (latest.type === 'node_started') return 'running';
  if (latest.type === 'node_completed') return 'done';
  if (latest.type === 'node_failed') return 'failed';
  return 'idle';
}
