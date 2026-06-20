import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Background,
  ControlButton,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeChange,
  type OnMoveEnd,
  applyNodeChanges,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Lock, Unlock } from 'lucide-react';
import { CrosscuttingNode } from './StageCompactNode';
import { StageCompactNode } from './StageCompactNode';
import type { CanvasLayout, InspectorTarget, QualityEvent, RunEvent, WorkflowDefinition } from '../types/workflow';

type Props = {
  workflow: WorkflowDefinition;
  selectedId: string;
  events: RunEvent[];
  onSelect: (target: InspectorTarget) => void;
  onLayoutChange: (layout: CanvasLayout) => void;
};

const nodeTypes = { stageCompact: StageCompactNode, crosscutting: CrosscuttingNode };
const crosscuttingTargetIds = ['summary', 'outline', 'detail', 'text'];

export function PipelineCanvas({ workflow, selectedId, events, onSelect, onLayoutChange }: Props) {
  const latestQuality = useMemo(() => {
    const map = new Map<string, QualityEvent>();
    events.forEach((event) => {
      if (event.type === 'quality_check_completed' && event.node_id && event.quality) {
        map.set(event.node_id, event.quality);
      }
    });
    return map;
  }, [events]);

  const workflowNodeKey = useMemo(
    () => workflow.nodes.map((stage) => `${stage.id}:${stage.label}:${stage.provider_profile_id}:${stage.model_settings.model}:${stage.quality_policy.min_score}`).join('|'),
    [workflow.nodes],
  );
  const layoutKey = useMemo(() => JSON.stringify(workflow.canvas_layout?.nodes ?? {}), [workflow.canvas_layout?.nodes]);
  const initialNodes = useMemo(() => buildNodes(workflow, selectedId, events, latestQuality), [events, latestQuality, layoutKey, selectedId, workflow.canvas_layout?.crosscutting_visible, workflowNodeKey]);
  const initialEdges = useMemo(() => buildEdges(workflow, events, selectedId), [events, selectedId, workflow.canvas_layout?.crosscutting_visible, workflow.edges, workflowNodeKey]);
  const [nodes, setNodes] = useNodesState(initialNodes);
  const [edges, setEdges] = useEdgesState(initialEdges);
  const [interactive, setInteractive] = useState(!(workflow.canvas_layout?.locked ?? false));

  useEffect(() => {
    setNodes((current) => mergeLayoutNodes(workflow, selectedId, events, latestQuality, current));
  }, [events, latestQuality, layoutKey, selectedId, setNodes, workflow.canvas_layout?.crosscutting_visible, workflowNodeKey]);

  useEffect(() => {
    setInteractive(!(workflow.canvas_layout?.locked ?? false));
  }, [workflow.canvas_layout?.locked]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  const persistLayout = useCallback((nextNodes: Node[], viewport = workflow.canvas_layout?.viewport, locked = workflow.canvas_layout?.locked ?? false) => {
    const layoutNodes = layoutFromNodes(workflow, nextNodes);
    onLayoutChange({
      nodes: layoutNodes,
      viewport,
      crosscutting_visible: workflow.canvas_layout?.crosscutting_visible ?? true,
      locked,
    });
  }, [onLayoutChange, workflow.canvas_layout?.crosscutting_visible, workflow.canvas_layout?.locked, workflow.canvas_layout?.viewport]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes, current));
  }, [setNodes]);

  const onMoveEnd = useCallback<OnMoveEnd>((_, viewport) => {
    persistLayout(nodes, viewport);
  }, [nodes, persistLayout]);

  return (
    <section className="canvas-shell">
      <div className="canvas-head">
        <div>
          <p className="eyebrow">Pipeline Canvas</p>
          <h2>创作阶段链路</h2>
        </div>
        <div className="pipeline-metrics">
          <span>{workflow.nodes.length} 阶段</span>
          <span>规划与正文约束</span>
          <span>质量阀门覆盖核心创作</span>
          <span>可拖拽/缩放</span>
        </div>
      </div>
      <div className="flow-frame">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          defaultViewport={workflow.canvas_layout?.viewport}
          fitView={!workflow.canvas_layout?.viewport}
          minZoom={0.45}
          maxZoom={1.25}
          nodesDraggable={interactive}
          panOnDrag={interactive}
          zoomOnDoubleClick={interactive}
          zoomOnPinch={interactive}
          zoomOnScroll={interactive}
          elementsSelectable={interactive}
          proOptions={{ hideAttribution: true }}
          onMoveEnd={onMoveEnd}
          onNodeClick={(_, node: Node) => {
            const stage = workflow.nodes.find((item) => item.id === node.id);
            if (stage) onSelect({ kind: 'stage', id: stage.id });
            if (node.id === 'wiki-layer') onSelect({ kind: 'wiki', id: 'wiki-layer' });
            if (node.id === 'quality-layer') onSelect({ kind: 'quality', id: 'quality-layer' });
          }}
          onNodeDragStop={(_, __, nextNodes) => persistLayout(nextNodes)}
          onNodesChange={onNodesChange}
        >
          <Background className="flow-bg" gap={22} size={1} />
          <MiniMap
            pannable
            zoomable
            ariaLabel=""
            className="mini-map"
            nodeStrokeWidth={2}
            nodeColor={(node) => (node.id === selectedId ? 'var(--accent)' : node.type === 'crosscutting' ? 'var(--accent-2)' : 'var(--node-mini)')}
            maskColor="var(--minimap-mask)"
          />
          <Controls
            showInteractive={false}
          >
            <ControlButton
              className="react-flow__controls-interactive"
              onClick={() => {
                const nextInteractive = !interactive;
                setInteractive(nextInteractive);
                persistLayout(nodes, workflow.canvas_layout?.viewport, !nextInteractive);
              }}
              title={interactive ? '锁定画布' : '解锁画布'}
              aria-label={interactive ? '锁定画布' : '解锁画布'}
            >
              {interactive ? <Unlock /> : <Lock />}
            </ControlButton>
          </Controls>
        </ReactFlow>
      </div>
    </section>
  );
}

function mergeLayoutNodes(
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

function layoutFromNodes(workflow: WorkflowDefinition, nextNodes: Node[]) {
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
    if (!current[id]) {
      current[id] = workflow.canvas_layout?.nodes?.[id] ?? defaultPosition(id, index);
    }
  }
  return current;
}

function buildNodes(
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

function buildEdges(workflow: WorkflowDefinition, events: RunEvent[], selectedId: string): Edge[] {
  const mainEdges = workflow.edges.map((edge) => ({
    ...edge,
    animated: events.some((event) => event.type === 'node_started' && event.node_id === edge.target),
    className: 'pipeline-edge',
    sourceHandle: 'bottom',
    targetHandle: 'top',
    type: 'smoothstep',
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
      type: 'smoothstep',
    },
    {
      id: `quality-${nodeId}`,
      source: 'quality-layer',
      target: nodeId,
      sourceHandle: 'left',
      targetHandle: 'right-target',
      animated: true,
      className: `crosscutting-edge quality-edge${selectedId === 'quality-layer' ? ' selected' : ''}`,
      type: 'smoothstep',
    },
  ]);
  return [...mainEdges, ...crosscutting];
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
