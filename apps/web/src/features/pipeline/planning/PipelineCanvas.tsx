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
import type { CanvasLayout, InspectorTarget, RunEvent, WorkflowDefinition } from '../contracts';
import { buildEdges, buildNodes, createCanvasLayout, createQualityMap, mergeLayoutNodes, pipelineNodeTypes } from './pipelineCanvasGraph';

type Props = {
  workflow: WorkflowDefinition;
  selectedId: string;
  events: RunEvent[];
  onSelect: (target: InspectorTarget) => void;
  onLayoutChange: (layout: CanvasLayout) => void;
};

export function PipelineCanvas({ workflow, selectedId, events, onSelect, onLayoutChange }: Props) {
  const latestQuality = useMemo(() => createQualityMap(events), [events]);

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
    onLayoutChange(createCanvasLayout(workflow, nextNodes, viewport, locked));
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
          nodeTypes={pipelineNodeTypes}
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
