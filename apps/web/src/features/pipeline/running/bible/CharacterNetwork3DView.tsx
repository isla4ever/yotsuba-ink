import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D, { type ForceGraphMethods } from 'react-force-graph-3d';
import { createCharacterNode3D, createRelationshipLabel3D, positionRelationshipLabel, relationshipCurve, relationshipCurveRotation, relationshipTouchesNode, type NodeLabelDetail } from './characterNetwork3DObjects';
import { createSpatialAnchorForce, initialSpatialLayout, networkCameraBounds, networkCameraDistance, networkCameraFrame, type SpatialNode } from './characterNetwork3DLayout';
import { tierNodeValue } from '../insights/characterGraphData';
import type { CharacterEdge, CharacterGraph, CharacterNode } from '../../contracts';

type Node3D = CharacterNode & { val: number };

type Props = {
  graph: CharacterGraph;
  /** Nodes outside the highlighted faction render in a muted neutral; same contract as the 2D view. */
  isNodeDimmed: (node: Pick<CharacterNode, 'faction' | 'faction_id'>) => boolean;
  cameraRequest?: { id: string; key: number; kind: 'fit' | 'focus' | 'zoom-in' | 'zoom-out' };
  accentColor: string;
  selectedId: string;
  onSelectNode: (nodeId: string) => void;
};

const dimmedNodeColor = '#3a4152';

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);
}

/**
 * Lazy-loaded 3D panorama of the character network — a browsing mode only:
 * clicking a node just syncs the shared selection (the dossier panel stays in
 * 2D land); editing flows never happen here. Performance contract: finite
 * cooldownTicks stops the force engine, the render loop is paused once settled
 * and only resumes while the pointer is over the canvas, and react-kapsule
 * invokes the underlying _destructor on unmount so no WebGL context survives
 * leaving the mode. There is no auto-rotation or any other self-driven motion,
 * so Reduced Motion needs no special casing.
 */
export function CharacterNetwork3DView({ accentColor, cameraRequest, graph, isNodeDimmed, onSelectNode, selectedId }: Props) {
  const graphRef = useRef<ForceGraphMethods>();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const engineReadyRef = useRef(false);
  const settledRef = useRef(false);
  const tickRef = useRef(0);
  const pauseTimerRef = useRef<number | null>(null);
  const [size, setSize] = useState({ width: 640, height: 480 });
  const activeFocusId = cameraRequest?.kind === 'fit' ? '' : cameraRequest?.id || selectedId;
  const compactViewport = size.width < 520;
  const portraitLayout = size.width / Math.max(1, size.height) < 1.25;

  const graphData = useMemo(() => {
    const positions = initialSpatialLayout(graph.nodes, portraitLayout ? 'portrait' : 'landscape');
    return {
      links: graph.edges.map((edge) => ({ ...edge })),
      nodes: graph.nodes.map<Node3D>((node, index) => ({
        ...node,
        ...positions[index],
        val: tierNodeValue(node),
      })),
    };
  }, [graph, portraitLayout]);

  const selectedNeighborhood = useMemo(() => {
    const ids = new Set<string>(selectedId ? [selectedId] : []);
    graph.edges.forEach((edge) => {
      if (edge.source === selectedId) ids.add(String(edge.target));
      if (edge.target === selectedId) ids.add(String(edge.source));
    });
    return ids;
  }, [graph.edges, selectedId]);

  const labelDetailFor = useCallback((nodeId: string): NodeLabelDetail => {
    if (graph.nodes.length <= 10 || selectedNeighborhood.has(nodeId)) return 'full';
    if (graph.nodes.length <= 20) return 'name';
    return 'hidden';
  }, [graph.nodes.length, selectedNeighborhood]);

  const resumeForCamera = useCallback((duration: number) => {
    if (!engineReadyRef.current) return;
    graphRef.current?.resumeAnimation?.();
    if (pauseTimerRef.current !== null) window.clearTimeout(pauseTimerRef.current);
    pauseTimerRef.current = window.setTimeout(() => {
      if (!wrapRef.current?.matches(':hover')) graphRef.current?.pauseAnimation?.();
    }, Math.max(80, duration + 80));
  }, []);

  const focusNetwork = useCallback((duration: number) => {
    const api = graphRef.current;
    if (!api || !engineReadyRef.current) return;
    resumeForCamera(duration);
    const frame = networkCameraFrame(graphData.nodes, size.width, size.height);
    api.cameraPosition(
      { x: frame.target.x, y: frame.target.y, z: frame.target.z + frame.distance },
      frame.target,
      duration,
    );
  }, [graphData.nodes, resumeForCamera, size.height, size.width]);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setSize({
        height: Math.max(260, Math.floor(entry.contentRect.height)),
        width: Math.max(280, Math.floor(entry.contentRect.width)),
      });
    });
    observer.observe(element);
    const frame = window.requestAnimationFrame(() => element.querySelector('canvas')?.setAttribute('tabindex', '-1'));
    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const api = graphRef.current;
    if (!api) return;
    api.d3Force('charge')?.strength?.(compactViewport ? -520 : -720);
    api.d3Force('link')?.distance?.(compactViewport ? 128 : 172);
    api.d3Force('center')?.strength?.(0.018);
    api.d3Force('spatialAnchor', createSpatialAnchorForce(graphData.nodes as SpatialNode[]));
    const fitDistance = networkCameraDistance(graphData.nodes as SpatialNode[], size.width, size.height);
    const bounds = networkCameraBounds(fitDistance);
    const controls = api.controls?.() as { maxDistance?: number; minDistance?: number } | undefined;
    if (controls) {
      controls.maxDistance = bounds.maximum;
      controls.minDistance = bounds.minimum;
    }
  }, [compactViewport, graphData, size.height, size.width]);

  useEffect(() => {
    const api = graphRef.current;
    if (!api || !engineReadyRef.current) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const selected = graphData.nodes.find((node) => node.id === activeFocusId) as SpatialNode | undefined;
    const frame = networkCameraFrame(graphData.nodes as SpatialNode[], size.width, size.height);
    const focusRatio = compactViewport ? 0.16 : 0.28;
    const focusTarget = selected && Number.isFinite(selected.x) && Number.isFinite(selected.y) && Number.isFinite(selected.z)
      ? {
          x: frame.target.x + ((selected.x ?? 0) - frame.target.x) * focusRatio,
          y: frame.target.y + ((selected.y ?? 0) - frame.target.y) * focusRatio,
          z: frame.target.z + ((selected.z ?? 0) - frame.target.z) * focusRatio,
        }
      : frame.target;
    if (cameraRequest?.kind === 'zoom-in' || cameraRequest?.kind === 'zoom-out') {
      const camera = api.camera();
      const factor = cameraRequest.kind === 'zoom-in' ? 0.78 : 1.28;
      const fitDistance = networkCameraDistance(graphData.nodes as SpatialNode[], size.width, size.height);
      const bounds = networkCameraBounds(fitDistance);
      const delta = {
        x: camera.position.x - focusTarget.x,
        y: camera.position.y - focusTarget.y,
        z: camera.position.z - focusTarget.z,
      };
      const currentDistance = Math.max(1, Math.hypot(delta.x, delta.y, delta.z));
      const nextDistance = Math.min(bounds.maximum, Math.max(bounds.minimum, currentDistance * factor));
      const boundedFactor = nextDistance / currentDistance;
      resumeForCamera(reduceMotion ? 0 : 280);
      api.cameraPosition({
        x: focusTarget.x + delta.x * boundedFactor,
        y: focusTarget.y + delta.y * boundedFactor,
        z: focusTarget.z + delta.z * boundedFactor,
      }, focusTarget, reduceMotion ? 0 : 280);
      return;
    }
    if (!activeFocusId || !selected || !Number.isFinite(selected.x) || !Number.isFinite(selected.y) || !Number.isFinite(selected.z)) {
      focusNetwork(reduceMotion ? 0 : 420);
      return;
    }
    const distance = frame.distance * (compactViewport ? 1 : 0.96);
    resumeForCamera(reduceMotion ? 0 : 420);
    api.cameraPosition(
      { x: focusTarget.x, y: focusTarget.y, z: focusTarget.z + distance },
      focusTarget,
      reduceMotion ? 0 : 420,
    );
  }, [activeFocusId, cameraRequest?.key, cameraRequest?.kind, compactViewport, focusNetwork, graphData, resumeForCamera, size.height, size.width]);

  useEffect(() => {
    tickRef.current = 0;
    settledRef.current = false;
    engineReadyRef.current = false;
  }, [graphData]);

  // Belt-and-braces on top of react-kapsule's unmount destructor: stop the frame loop first.
  useEffect(
    () => () => {
      if (pauseTimerRef.current !== null) window.clearTimeout(pauseTimerRef.current);
      graphRef.current?.pauseAnimation?.();
    },
    [],
  );

  return (
    <div
      aria-label="人物关系 3D 全景画布"
      className="bible-network-3d-canvas"
      onPointerEnter={() => {
        if (engineReadyRef.current) graphRef.current?.resumeAnimation?.();
      }}
      onPointerLeave={() => {
        if (settledRef.current) graphRef.current?.pauseAnimation?.();
      }}
      ref={wrapRef}
      role="region"
    >
      <ForceGraph3D
        ref={graphRef}
        graphData={graphData}
        width={size.width}
        height={size.height}
        backgroundColor="rgba(0,0,0,0)"
        showNavInfo={false}
        cooldownTicks={120}
        warmupTicks={42}
        enableNodeDrag
        nodeThreeObject={(node: object) => {
          const item = node as Node3D;
          const color = isNodeDimmed(item) ? dimmedNodeColor : accentColor;
          return createCharacterNode3D(item, color, item.id === selectedId, {
            compact: compactViewport,
            labelDetail: labelDetailFor(item.id),
          });
        }}
        nodeThreeObjectExtend
        nodeVal={(node) => (node as Node3D).val}
        nodeRelSize={7}
        nodeColor={(node) => {
          const item = node as Node3D;
          if (item.id === selectedId) return accentColor;
          return isNodeDimmed(item) ? dimmedNodeColor : accentColor;
        }}
        nodeLabel={(node) => {
          const item = node as Node3D;
          return escapeHtml([item.name, item.role].filter((part) => part.trim()).join(' · '));
        }}
        nodeOpacity={0}
        linkColor={() => accentColor}
        linkWidth={(link) => 0.75 + Number((link as CharacterEdge).strength ?? 0.5) * 1.9}
        linkOpacity={0.5}
        linkCurvature={(link) => relationshipCurve(link as CharacterEdge)}
        linkCurveRotation={(link) => relationshipCurveRotation(link as CharacterEdge)}
        linkDirectionalParticles={0}
        linkDirectionalArrowLength={4.2}
        linkDirectionalArrowRelPos={0.94}
        linkThreeObjectExtend
        linkThreeObject={(link) => {
          const edge = link as CharacterEdge;
          return createRelationshipLabel3D(edge, accentColor, {
            compact: compactViewport,
            visible: graphData.links.length <= 3 || relationshipTouchesNode(edge, selectedId),
          });
        }}
        linkPositionUpdate={(object, { start, end }) => {
          return positionRelationshipLabel(object, start, end);
        }}
        onEngineTick={() => {
          engineReadyRef.current = true;
          tickRef.current += 1;
          if (!activeFocusId && tickRef.current === 18) {
            const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            focusNetwork(reduceMotion ? 0 : 440);
          }
        }}
        onEngineStop={() => {
          engineReadyRef.current = true;
          settledRef.current = true;
          const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          if (!activeFocusId) focusNetwork(reduceMotion ? 0 : 520);
          if (pauseTimerRef.current !== null) window.clearTimeout(pauseTimerRef.current);
          pauseTimerRef.current = window.setTimeout(() => {
            if (!wrapRef.current?.matches(':hover')) graphRef.current?.pauseAnimation?.();
          }, reduceMotion ? 0 : 560);
        }}
        onNodeClick={(node) => onSelectNode((node as Node3D).id)}
        onBackgroundClick={() => onSelectNode('')}
      />
    </div>
  );
}

export { initialSpatialLayout, networkCameraBounds, networkCameraDistance, networkCameraFrame } from './characterNetwork3DLayout';
