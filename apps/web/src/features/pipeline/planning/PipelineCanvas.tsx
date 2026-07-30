import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import {
  Background,
  ControlButton,
  Controls,
  MiniMap,
  ReactFlow,
  type ReactFlowInstance,
  type Edge,
  type Node,
  type NodeChange,
  type OnMoveEnd,
  applyNodeChanges,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Layers3, Lock, Network, Unlock } from 'lucide-react';
import type { CanvasLayout, InspectorTarget, RunEvent, WorkflowDefinition } from '../contracts';
import { canvasFitPadding, shouldAutoCenterCanvas } from '../lib/canvasViewport';
import {
  buildEdges,
  buildNodes,
  createCanvasLayout,
  createQualityMap,
  isCanvasNodeActivationKey,
  isCanvasViewportInteractive,
  mergeLayoutNodes,
  pipelineNodeTypes,
  type PipelineLayoutVariant,
} from './pipelineCanvasGraph';
import { PlanningStageNavigator } from './PlanningStageNavigator';
import { ArtifactDeck } from './ArtifactDeck';
import { buildPlanningStagePosition } from './artifactDeckModel';

type Props = {
  workflow: WorkflowDefinition;
  selectedId: string;
  events: RunEvent[];
  onSelect: (target: InspectorTarget) => void;
  onLayoutChange: (layout: CanvasLayout) => void;
  mode?: 'planning' | 'cockpit';
  layoutVariant?: PipelineLayoutVariant;
  onNodeDoubleClick?: (stageId: string) => void;
  lockedViewport?: boolean;
  runtimeLayersEnabled?: boolean;
  onOpenStageConfig?: () => void;
};

export function PipelineCanvas({
  workflow,
  selectedId,
  events,
  onSelect,
  onLayoutChange,
  mode = 'planning',
  layoutVariant = 'planning',
  onNodeDoubleClick,
  lockedViewport = false,
  runtimeLayersEnabled = true,
  onOpenStageConfig,
}: Props) {
  const latestQuality = useMemo(() => createQualityMap(events), [events]);
  const showCrosscutting = layoutVariant === 'cockpit-vertical' && workflow.canvas_layout?.crosscutting_visible !== false;
  const flowRef = useRef<ReactFlowInstance<Node, Edge> | null>(null);
  const flowFrameRef = useRef<HTMLDivElement | null>(null);
  const autoFitKeyRef = useRef<string>('');
  const nodeClickTimerRef = useRef<number | null>(null);
  const [flowReady, setFlowReady] = useState(false);
  const [canvasView, setCanvasView] = useState<'deck' | 'graph'>('deck');

  const workflowNodeKey = useMemo(
    () => workflow.nodes.map((stage) => `${stage.id}:${stage.label}:${stage.provider_profile_id}:${stage.model_settings.model}:${stage.quality_policy.min_score}:${JSON.stringify(stage.input_schema.map((field) => field.default))}`).join('|'),
    [workflow.nodes],
  );
  const layoutKey = useMemo(() => JSON.stringify(workflow.canvas_layout?.nodes ?? {}), [workflow.canvas_layout?.nodes]);
  const runFitKey = useMemo(
    () => events.filter((event) => event.node_id && (event.type.startsWith('node_') || event.type === 'stage_checkpoint_ready')).map((event) => `${event.type}:${event.node_id}`).slice(0, 8).join('|'),
    [events],
  );
  const initialNodes = useMemo(() => buildNodes(workflow, selectedId, events, latestQuality, showCrosscutting, layoutVariant, runtimeLayersEnabled), [events, latestQuality, layoutKey, layoutVariant, runtimeLayersEnabled, selectedId, showCrosscutting, workflowNodeKey]);
  const initialEdges = useMemo(() => buildEdges(workflow, events, selectedId, showCrosscutting, layoutVariant, runtimeLayersEnabled), [events, layoutVariant, runtimeLayersEnabled, selectedId, showCrosscutting, workflow.edges, workflowNodeKey]);
  const [nodes, setNodes] = useNodesState(initialNodes);
  const [edges, setEdges] = useEdgesState(initialEdges);
  const [layoutLocked, setLayoutLocked] = useState(workflow.canvas_layout?.locked ?? false);
  const viewportInteractive = isCanvasViewportInteractive(lockedViewport, layoutLocked);

  const fitCanvasToFrame = useCallback((duration = 180) => {
    const frame = flowFrameRef.current;
    const width = frame?.clientWidth ?? 0;
    const height = frame?.clientHeight ?? 0;
    if (!flowRef.current || !width || !height) return;
    flowRef.current.fitView({
      padding: canvasFitPadding(width, height),
      duration,
      includeHiddenNodes: false,
      minZoom: layoutVariant === 'cockpit-vertical' ? (width >= 700 ? 0.6 : 0.5) : width >= 1600 ? 0.52 : width >= 1300 ? 0.4 : 0.34,
      maxZoom: 1,
    });
  }, [layoutVariant]);

  useEffect(() => {
    setNodes((current) => mergeLayoutNodes(workflow, selectedId, events, latestQuality, current, showCrosscutting, layoutVariant, runtimeLayersEnabled));
  }, [events, latestQuality, layoutKey, layoutVariant, runtimeLayersEnabled, selectedId, setNodes, showCrosscutting, workflowNodeKey]);

  useEffect(() => {
    setLayoutLocked(workflow.canvas_layout?.locked ?? false);
  }, [workflow.canvas_layout?.locked]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  useEffect(() => {
    const autoFitKey = `${workflow.id}:${layoutVariant}:${layoutKey}:${workflowNodeKey}`;
    if (!flowRef.current || autoFitKeyRef.current === autoFitKey || !shouldAutoCenterCanvas(nodes)) return;
    autoFitKeyRef.current = autoFitKey;
    window.requestAnimationFrame(() => fitCanvasToFrame(220));
  }, [fitCanvasToFrame, layoutKey, layoutVariant, nodes.length, workflow.id, workflowNodeKey]);

  useEffect(() => {
    if (layoutVariant !== 'cockpit-vertical' || !flowRef.current || !runFitKey) return;
    window.requestAnimationFrame(() => fitCanvasToFrame(160));
  }, [fitCanvasToFrame, layoutVariant, runFitKey]);

  useEffect(() => {
    const frame = flowFrameRef.current;
    if (!frame) return;
    let frameId = 0;
    const syncFlowReady = () => {
      const hasSize = frame.clientWidth > 0 && frame.clientHeight > 0;
      setFlowReady(hasSize);
      if (hasSize) fitCanvasToFrame(140);
    };
    const observer = new ResizeObserver(() => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(syncFlowReady);
    });
    observer.observe(frame);
    frameId = window.requestAnimationFrame(syncFlowReady);
    return () => {
      window.cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, [canvasView, fitCanvasToFrame]);

  useEffect(() => {
    return () => {
      if (nodeClickTimerRef.current) {
        window.clearTimeout(nodeClickTimerRef.current);
      }
    };
  }, []);

  const persistLayout = useCallback((nextNodes: Node[], viewport = workflow.canvas_layout?.viewport, locked = workflow.canvas_layout?.locked ?? false) => {
    if (lockedViewport) return;
    onLayoutChange(createCanvasLayout(workflow, nextNodes, viewport, locked));
  }, [lockedViewport, onLayoutChange, workflow.canvas_layout?.crosscutting_visible, workflow.canvas_layout?.locked, workflow.canvas_layout?.viewport]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes, current));
  }, [setNodes]);

  const onMoveEnd = useCallback<OnMoveEnd>((event, viewport) => {
    if (!event) return;
    persistLayout(nodes, viewport);
  }, [nodes, persistLayout]);

  const selectNode = useCallback((node: Node) => {
    const stage = workflow.nodes.find((item) => item.id === node.id);
    if (stage) onSelect({ kind: 'stage', id: stage.id });
    if (runtimeLayersEnabled && node.id === 'wiki-layer') onSelect({ kind: 'wiki', id: 'wiki-layer' });
    if (runtimeLayersEnabled && node.id === 'quality-layer') onSelect({ kind: 'quality', id: 'quality-layer' });
  }, [onSelect, runtimeLayersEnabled, workflow.nodes]);

  const handleNodeKeyDown = useCallback((event: KeyboardEvent<HTMLDivElement>) => {
    if (!isCanvasNodeActivationKey(event.key) || !(event.target instanceof Element)) return;
    const nodeElement = event.target.closest<HTMLElement>('.react-flow__node[data-id]');
    if (!nodeElement || !event.currentTarget.contains(nodeElement)) return;
    const node = nodes.find((item) => item.id === nodeElement.dataset.id);
    if (!node || node.focusable === false || node.selectable === false) return;
    event.preventDefault();
    event.stopPropagation();
    selectNode(node);
  }, [nodes, selectNode]);

  return (
    <section className={`canvas-shell ${mode === 'planning' ? 'planning-canvas-shell' : 'cockpit-canvas-shell'} ${layoutVariant === 'cockpit-vertical' ? 'vertical-cockpit-canvas' : ''} canvas-view-${canvasView}`}>
      <div className="canvas-head">
        <div>
          <p className="eyebrow">创作流程</p>
          <h2>{canvasView === 'deck' ? '七阶段稿件栈' : '创作阶段流程'}</h2>
        </div>
        <div className="pipeline-metrics">
          <CanvasStagePosition events={events} selectedId={selectedId} workflow={workflow} />
          <div aria-label="流程视图" className="canvas-view-switch" role="group">
            <button aria-pressed={canvasView === 'deck'} onClick={() => setCanvasView('deck')} title="稿件栈视图" type="button"><Layers3 size={14} /><span>稿件栈</span></button>
            <button aria-pressed={canvasView === 'graph'} onClick={() => setCanvasView('graph')} title="流程图视图" type="button"><Network size={14} /><span>流程图</span></button>
          </div>
        </div>
      </div>
      {canvasView === 'graph' && mode === 'planning' ? (
        <PlanningStageNavigator
          onOpenConfig={onOpenStageConfig}
          onSelect={onSelect}
          selectedId={selectedId}
          stages={workflow.nodes}
        />
      ) : null}
      {canvasView === 'deck' ? (
        <ArtifactDeck
          events={events}
          onOpenConfig={onOpenStageConfig}
          onOpenStage={onNodeDoubleClick}
          onSelect={onSelect}
          selectedId={selectedId}
          workflow={workflow}
        />
      ) : <div className="flow-frame" onKeyDownCapture={handleNodeKeyDown} ref={flowFrameRef}>
        {flowReady ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={pipelineNodeTypes}
            fitView
            minZoom={0.32}
            maxZoom={1.25}
            nodesDraggable={viewportInteractive}
            panOnDrag={viewportInteractive}
            zoomOnDoubleClick={viewportInteractive && !onNodeDoubleClick}
            zoomOnPinch={viewportInteractive}
            zoomOnScroll={viewportInteractive}
            elementsSelectable
            proOptions={{ hideAttribution: true }}
            onInit={(instance) => {
              flowRef.current = instance;
              window.requestAnimationFrame(() => fitCanvasToFrame(0));
            }}
            onMoveEnd={onMoveEnd}
            onNodeClick={(_, node: Node) => {
              if (nodeClickTimerRef.current) {
                window.clearTimeout(nodeClickTimerRef.current);
              }
              if (onNodeDoubleClick) {
                nodeClickTimerRef.current = window.setTimeout(() => {
                  nodeClickTimerRef.current = null;
                  selectNode(node);
                }, 220);
                return;
              }
              selectNode(node);
            }}
            onNodeDoubleClick={(_, node: Node) => {
              if (nodeClickTimerRef.current) {
                window.clearTimeout(nodeClickTimerRef.current);
                nodeClickTimerRef.current = null;
              }
              const stage = workflow.nodes.find((item) => item.id === node.id);
              if (stage) onNodeDoubleClick?.(stage.id);
            }}
            onNodeDragStop={(_, __, nextNodes) => persistLayout(nextNodes)}
            onNodesChange={onNodesChange}
          >
            <Background className="flow-bg" gap={22} size={1} />
            <MiniMap
              pannable={viewportInteractive}
              zoomable={viewportInteractive}
              ariaLabel="创作流程缩略图"
              className="mini-map"
              position="bottom-right"
              nodeStrokeWidth={2}
              nodeColor={(node) => (node.id === selectedId ? 'var(--accent)' : node.type === 'crosscutting' ? 'var(--accent-2)' : 'var(--node-mini)')}
              maskColor="var(--minimap-mask)"
            />
            <Controls
              showInteractive={false}
            >
              {!lockedViewport ? (
                <ControlButton
                  className="react-flow__controls-interactive"
                  onClick={() => {
                    const nextLocked = !layoutLocked;
                    setLayoutLocked(nextLocked);
                    persistLayout(nodes, workflow.canvas_layout?.viewport, nextLocked);
                  }}
                  title={layoutLocked ? '解锁画布' : '锁定画布'}
                  aria-label={layoutLocked ? '解锁画布' : '锁定画布'}
                >
                  {layoutLocked ? <Lock /> : <Unlock />}
                </ControlButton>
              ) : null}
            </Controls>
          </ReactFlow>
        ) : null}
      </div>}
    </section>
  );
}

/**
 * Phase 12 D4/Wave 4: the canvas aggregate shares Cover/Export delivery
 * truth with the cards, sidebar and Header.
 */
function CanvasStagePosition({
  events,
  selectedId,
  workflow,
}: {
  events: RunEvent[];
  selectedId: string;
  workflow: WorkflowDefinition;
}) {
  const position = buildPlanningStagePosition(workflow, events, selectedId);
  if (!position.completed && !position.current) return <span>{workflow.nodes.length} 阶段</span>;
  return (
    <span>
      第 {position.current || 1}/{position.total} 阶段
      {position.completed ? ` · 已完成 ${position.completed}` : ''}
    </span>
  );
}
