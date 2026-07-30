import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { edgeHoverText } from './characterNetworkModel';
import { drawCharacterNode, drawRelationLayer, getCssVar, graphFitPadding, idForEndpoint, linkKey } from '../insights/characterGraphCanvas';
import { tierNodeValue, tierRingLayout, unaffiliatedColor } from '../insights/characterGraphData';
import type { GraphLink, GraphNode } from '../insights/characterGraphTypes';
import type { CharacterGraph } from '../../contracts';

type Props = {
  graph: CharacterGraph;
  accentColor: string;
  /** Nodes outside the highlighted faction render dimmed; empty highlight keeps everything full strength. */
  isNodeDimmed: (node: GraphNode) => boolean;
  selectedId: string;
  onSelectNode: (nodeId: string) => void;
};

const idleHint = '点击节点查看人物档案，悬停连线查看关系语义';

/**
 * Story Bible full-page character network. Static-friendly by contract: the
 * simulation cools down and autoPauseRedraw stops the RAF loop once settled;
 * there are no idle particles or decorative layers.
 */
export function CharacterNetworkView({ accentColor, graph, isNodeDimmed, onSelectNode, selectedId }: Props) {
  const graphRef = useRef<ForceGraphMethods>();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const hoveredNodeRef = useRef<string | null>(null);
  const hoveredLinkRef = useRef<string | null>(null);
  const [hovered, setHovered] = useState(idleHint);
  const [graphSize, setGraphSize] = useState({ width: 640, height: 480 });
  const graphKey = useMemo(() => graphSignature(graph), [graph]);

  const graphData = useMemo<{ nodes: GraphNode[]; links: GraphLink[] }>(() => {
    const positions = tierRingLayout(graph.nodes);
    return {
      links: graph.edges.map((edge) => ({ ...edge })),
      nodes: graph.nodes.map((node, index) => ({
        ...node,
        ...positions[index],
        color: node.faction?.trim() ? accentColor : unaffiliatedColor,
        val: tierNodeValue(node),
      })),
    };
  }, [accentColor, graphKey]);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setGraphSize({
        height: Math.max(360, Math.floor(entry.contentRect.height)),
        width: Math.max(320, Math.floor(entry.contentRect.width)),
      });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const graphApi = graphRef.current;
    if (!graphApi) return;
    graphApi.d3Force('charge')?.strength?.(-420);
    graphApi.d3Force('link')?.distance?.(210);
    graphApi.d3Force('center')?.strength?.(0.04);
    graphApi.d3Force('spread', (alpha: number) => {
      graphData.nodes.forEach((node) => {
        node.vx = (node.vx ?? 0) + (node.initialX - (node.x ?? 0)) * alpha * 0.075;
        node.vy = (node.vy ?? 0) + (node.initialY - (node.y ?? 0)) * alpha * 0.075;
      });
    });
    graphApi.d3ReheatSimulation?.();
    const timer = window.setTimeout(() => {
      graphApi.zoomToFit?.(420, graphFitPadding(graphSize.width, graphSize.height));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [graphData.nodes, graphKey, graphSize.height, graphSize.width]);

  return (
    <div aria-hidden="true" className="bible-network-canvas" ref={wrapRef}>
      <div className="graph-hover-float bible-network-hover">{hovered}</div>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={graphSize.width}
        height={graphSize.height}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={96}
        d3AlphaDecay={0.032}
        d3VelocityDecay={0.24}
        nodeRelSize={1.75}
        linkDirectionalParticles={0}
        linkWidth={(link) => 0.65 + Number((link as GraphLink).strength ?? 0.5) * 1.05}
        linkColor={(link) => (linkKey(link as GraphLink) === hoveredLinkRef.current ? getCssVar('--accent-2') : getCssVar('--edge'))}
        autoPauseRedraw
        linkCanvasObjectMode={() => 'after'}
        linkCanvasObject={(link, ctx, globalScale) => drawRelationLayer(link as GraphLink, ctx, globalScale, linkKey(link as GraphLink) === hoveredLinkRef.current)}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const graphNode = node as GraphNode;
          const dimmed = isNodeDimmed(graphNode);
          ctx.save();
          ctx.globalAlpha = dimmed ? 0.16 : 1;
          drawCharacterNode(graphNode, ctx, globalScale, hoveredNodeRef.current === graphNode.id || selectedId === graphNode.id);
          ctx.restore();
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, 11, 0, 2 * Math.PI, false);
          ctx.fill();
        }}
        onEngineStop={() => {
          graphRef.current?.zoomToFit?.(320, graphFitPadding(graphSize.width, graphSize.height));
        }}
        onNodeHover={(node) => {
          hoveredNodeRef.current = node ? (node as GraphNode).id : null;
          setHovered(node ? `${(node as GraphNode).name} · ${(node as GraphNode).role}` : idleHint);
        }}
        onLinkHover={(link) => {
          const graphLink = link as GraphLink | null;
          hoveredLinkRef.current = graphLink ? linkKey(graphLink) : null;
          setHovered(
            graphLink
              ? edgeHoverText(graph, { ...graphLink, source: idForEndpoint(graphLink.source), target: idForEndpoint(graphLink.target) })
              : idleHint,
          );
        }}
        onNodeClick={(node) => onSelectNode((node as GraphNode).id)}
        onBackgroundClick={() => onSelectNode('')}
      />
    </div>
  );
}

function graphSignature(graph: CharacterGraph) {
  return JSON.stringify({
    edges: graph.edges.map((edge) => [edge.source, edge.target, edge.relation, edge.strength, edge.kind ?? '', edge.polarity ?? '']),
    nodes: graph.nodes.map((node) => [node.id, node.name, node.role, node.faction, node.status, node.tier ?? '']),
  });
}
