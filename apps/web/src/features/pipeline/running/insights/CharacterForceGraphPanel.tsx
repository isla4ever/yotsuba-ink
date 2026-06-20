import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { Network, X } from 'lucide-react';
import type { CharacterGraph, CharacterNode, RunEvent } from '../../contracts';

type Props = {
  events: RunEvent[];
};

type GraphNode = CharacterNode & {
  val: number;
  color: string;
  initialX: number;
  initialY: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
};

type GraphLink = {
  source: string;
  target: string;
  relation: string;
  strength: number;
};

const fallback: CharacterGraph = {
  updated_by: 'mock',
  nodes: [
    { id: 'c1', name: '林雾', role: '主角', faction: '旧港调查线', status: '追查记忆失真' },
    { id: 'c2', name: '沈白', role: '盟友/嫌疑人', faction: '档案馆', status: '掌握旧案碎片' },
    { id: 'c3', name: '周砚', role: '对手', faction: '港务集团', status: '隐藏关键证据' },
    { id: 'c4', name: '阿青', role: '线索人物', faction: '码头旧友', status: '关系摇摆' },
    { id: 'c5', name: '许檀', role: '幕后推动者', faction: '记忆实验室', status: '目的未明' },
  ],
  edges: [
    { source: 'c1', target: 'c2', relation: '互信未稳', strength: 0.62 },
    { source: 'c1', target: 'c3', relation: '调查/压制', strength: 0.78 },
    { source: 'c2', target: 'c5', relation: '旧案关联', strength: 0.54 },
    { source: 'c3', target: 'c5', relation: '利益同盟', strength: 0.7 },
    { source: 'c1', target: 'c4', relation: '童年旧识', strength: 0.66 },
  ],
};

const factionColors = ['#2f7df6', '#18b6c8', '#26c985', '#e8b44c', '#9b7cff'];

export function CharacterForceGraphPanel({ events }: Props) {
  const graphRef = useRef<ForceGraphMethods>();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const hoveredNodeRef = useRef<string | null>(null);
  const hoveredLinkRef = useRef<string | null>(null);
  const [hovered, setHovered] = useState<string>('拖拽节点查看人物关系');
  const [selected, setSelected] = useState<CharacterNode | null>(null);
  const [graphSize, setGraphSize] = useState({ width: 360, height: 240 });
  const lastClickRef = useRef<{ id: string; at: number } | null>(null);
  const latest = events.find((event) => event.type === 'character_graph_updated' && event.character_graph);
  const graph = latest?.character_graph ?? fallback;

  const graphData = useMemo<{ nodes: GraphNode[]; links: GraphLink[] }>(() => {
    const factions = Array.from(new Set(graph.nodes.map((node) => node.faction)));
    return {
      nodes: graph.nodes.map((node, index) => ({
        ...node,
        ...initialPosition(index),
        val: node.role.includes('主角') ? 5.4 : 4.2,
        color: factionColors[Math.max(0, factions.indexOf(node.faction)) % factionColors.length],
      })),
      links: graph.edges.map((edge) => ({ ...edge })),
    };
  }, [graph]);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(280, Math.floor(entry.contentRect.width));
      const height = Math.max(220, Math.floor(entry.contentRect.height));
      setGraphSize({ width, height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const graphApi = graphRef.current;
    if (!graphApi) return;
    graphApi.d3Force('charge')?.strength?.(-280);
    graphApi.d3Force('link')?.distance?.(150);
    graphApi.d3Force('center')?.strength?.(0.022);
    graphApi.d3Force('spread', (alpha: number) => {
      graphData.nodes.forEach((node) => {
        node.vx = (node.vx ?? 0) + (node.initialX - (node.x ?? 0)) * alpha * 0.07;
        node.vy = (node.vy ?? 0) + (node.initialY - (node.y ?? 0)) * alpha * 0.07;
      });
    });
    graphApi.d3ReheatSimulation?.();
    window.setTimeout(() => graphApi.zoomToFit?.(360, 42), 120);
  }, [graphData]);

  return (
    <section className="insight-card character-card">
      <div className="insight-card-head">
        <div>
          <p className="eyebrow">Character Graph</p>
          <h3><Network size={16} />人物关系网</h3>
        </div>
        <div className="rail-metrics">
          <span>{graph.nodes.length} 人物</span>
          <span>{graph.edges.length} 关系</span>
        </div>
      </div>
      <div className="force-graph-wrap" ref={wrapRef}>
        <div className="graph-hover-float">{hovered}</div>
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          width={graphSize.width}
          height={graphSize.height}
          backgroundColor="rgba(0,0,0,0)"
          cooldownTicks={120}
          d3AlphaDecay={0.026}
          d3VelocityDecay={0.2}
          nodeRelSize={1.75}
          linkDirectionalParticles={0}
          linkDirectionalParticleSpeed={(link) => 0.004 + Number((link as GraphLink).strength ?? 0.5) * 0.004}
          linkWidth={(link) => 0.65 + Number((link as GraphLink).strength ?? 0.5) * 1.05}
          linkColor={(link) => linkKey(link as GraphLink) === hoveredLinkRef.current ? getCssVar('--accent-2') : getCssVar('--edge')}
          autoPauseRedraw={false}
          linkCanvasObjectMode={() => 'after'}
          linkCanvasObject={(link, ctx, globalScale) => drawRelationLayer(link as GraphLink, ctx, globalScale, linkKey(link as GraphLink) === hoveredLinkRef.current)}
          nodeCanvasObject={(node, ctx, globalScale) => drawCharacterNode(node as GraphNode, ctx, globalScale, hoveredNodeRef.current === (node as GraphNode).id)}
          nodePointerAreaPaint={(node, color, ctx) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, 10, 0, 2 * Math.PI, false);
            ctx.fill();
          }}
          onEngineStop={() => graphRef.current?.zoomToFit?.(320, 42)}
          onNodeHover={(node) => {
            hoveredNodeRef.current = node ? (node as GraphNode).id : null;
            setHovered(node ? `${(node as GraphNode).name} · ${(node as GraphNode).role}` : '拖拽节点查看人物关系');
          }}
          onLinkHover={(link) => {
            hoveredLinkRef.current = link ? linkKey(link as GraphLink) : null;
            setHovered(link ? `${nameFor(graph, idForEndpoint((link as GraphLink).source))} → ${nameFor(graph, idForEndpoint((link as GraphLink).target))} · ${(link as GraphLink).relation}` : '拖拽节点查看人物关系');
          }}
          onNodeClick={(node) => {
            const graphNode = node as GraphNode;
            const now = Date.now();
            if (lastClickRef.current?.id === graphNode.id && now - lastClickRef.current.at < 320) {
              setSelected(graphNode);
              lastClickRef.current = null;
              return;
            }
            lastClickRef.current = { id: graphNode.id, at: now };
          }}
        />
      </div>
      {selected ? <CharacterRelationModal graph={graph} node={selected} onClose={() => setSelected(null)} /> : null}
    </section>
  );
}

function drawCharacterNode(node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number, hovered: boolean) {
  const label = node.name.slice(0, 1);
  const pulse = 1 + Math.sin(Date.now() / 720 + node.initialX * 0.01) * 0.05;
  const radius = (node.val + 1.8) * (hovered ? 1.18 : 1);
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const innerColor = softenColor(node.color);
  ctx.beginPath();
  ctx.arc(x, y, radius + 3.4 * pulse, 0, 2 * Math.PI, false);
  ctx.fillStyle = `${node.color}2e`;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x, y, radius + 5.6 * pulse, 0, 2 * Math.PI, false);
  ctx.strokeStyle = `${node.color}${hovered ? '88' : '36'}`;
  ctx.lineWidth = hovered ? 1.4 : 0.8;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
  ctx.fillStyle = innerColor;
  ctx.fill();
  ctx.strokeStyle = node.color;
  ctx.lineWidth = 1.3;
  ctx.stroke();
  const fontSize = Math.max(6.8, Math.min(radius * 1.08, 9.2 / globalScale));
  ctx.font = `700 ${fontSize}px Inter, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = textColorFor(innerColor);
  ctx.fillText(label, x, y);
}

function nameFor(graph: CharacterGraph, id: string) {
  return graph.nodes.find((node) => node.id === id)?.name ?? id;
}

function drawRelationLayer(link: GraphLink, ctx: CanvasRenderingContext2D, globalScale: number, hovered: boolean) {
  drawRelationGlow(link, ctx, hovered);
  drawRelationLabel(link, ctx, globalScale, hovered);
}

function drawRelationGlow(link: GraphLink, ctx: CanvasRenderingContext2D, hovered: boolean) {
  const source = link.source as unknown as GraphNode;
  const target = link.target as unknown as GraphNode;
  if (typeof source === 'string' || typeof target === 'string') return;
  const startX = source.x ?? 0;
  const startY = source.y ?? 0;
  const endX = target.x ?? 0;
  const endY = target.y ?? 0;
  const progress = (Date.now() / 1800 + link.strength) % 1;
  const x = startX + (endX - startX) * progress;
  const y = startY + (endY - startY) * progress;
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, hovered ? 2.4 : 1.6, 0, 2 * Math.PI, false);
  ctx.fillStyle = hovered ? getCssVar('--accent-2') : 'rgba(255,255,255,0.58)';
  ctx.shadowColor = getCssVar('--accent-2');
  ctx.shadowBlur = hovered ? 10 : 5;
  ctx.fill();
  ctx.restore();
}

function drawRelationLabel(link: GraphLink, ctx: CanvasRenderingContext2D, globalScale: number, hovered: boolean) {
  const source = link.source as unknown as GraphNode;
  const target = link.target as unknown as GraphNode;
  if (typeof source === 'string' || typeof target === 'string') return;
  const startX = source.x ?? 0;
  const startY = source.y ?? 0;
  const endX = target.x ?? 0;
  const endY = target.y ?? 0;
  const x = (startX + endX) / 2;
  const y = (startY + endY) / 2;
  const label = link.relation;
  if (!hovered && globalScale < 0.78 && link.strength < 0.66) return;
  const fontSize = hovered ? Math.max(5, 5.8 / globalScale) : Math.max(4.2, 5 / globalScale);
  ctx.font = `700 ${fontSize}px Inter, sans-serif`;
  const width = ctx.measureText(label).width + 6;
  ctx.fillStyle = hovered ? getCssVar('--graph-label-bg-strong') : getCssVar('--graph-label-bg');
  roundRect(ctx, x - width / 2, y - fontSize / 2 - 2, width, fontSize + 4, 4);
  ctx.fill();
  ctx.fillStyle = getCssVar('--graph-label-text') || getCssVar('--text-soft');
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, x, y);
}

function linkKey(link: GraphLink) {
  return `${idForEndpoint(link.source)}-${idForEndpoint(link.target)}-${link.relation}`;
}

function idForEndpoint(endpoint: GraphLink['source'] | GraphLink['target']) {
  return typeof endpoint === 'string' ? endpoint : (endpoint as GraphNode).id;
}

function CharacterRelationModal({ graph, node, onClose }: { graph: CharacterGraph; node: CharacterNode; onClose: () => void }) {
  const relations = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  return (
    <div className="character-modal-backdrop" onClick={onClose}>
      <article className="character-modal" onClick={(event) => event.stopPropagation()}>
        <button className="modal-close" onClick={onClose} title="关闭"><X size={15} /></button>
        <p className="eyebrow">Character Relation</p>
        <h3>{node.name}</h3>
        <div className="modal-meta">
          <span>{node.role}</span>
          <span>{node.faction}</span>
          <span>{node.status}</span>
        </div>
        <div className="relation-list">
          {relations.map((edge) => {
            const otherId = edge.source === node.id ? edge.target : edge.source;
            return (
              <section key={`${edge.source}-${edge.target}`}>
                <strong>{node.name} → {nameFor(graph, otherId)}</strong>
                <span>{edge.relation} · 强度 {Math.round(edge.strength * 100)}%</span>
              </section>
            );
          })}
        </div>
      </article>
    </div>
  );
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + width, y, x + width, y + height, radius);
  ctx.arcTo(x + width, y + height, x, y + height, radius);
  ctx.arcTo(x, y + height, x, y, radius);
  ctx.arcTo(x, y, x + width, y, radius);
  ctx.closePath();
}

function getCssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function initialPosition(index: number) {
  const points = [
    { x: -220, y: -84 },
    { x: -176, y: 112 },
    { x: 22, y: -12 },
    { x: 188, y: -104 },
    { x: 226, y: 112 },
    { x: -20, y: 154 },
    { x: 48, y: -160 },
  ];
  const point = points[index % points.length];
  return { initialX: point.x, initialY: point.y, x: point.x, y: point.y };
}

function softenColor(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  const mix = (value: number) => Math.round(value * 0.82 + 255 * 0.18);
  return rgbToHex(mix(r), mix(g), mix(b));
}

function textColorFor(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  const luminance = (0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b));
  return luminance > 0.48 ? '#07111f' : '#f8fbff';
}

function channel(value: number) {
  const normalized = value / 255;
  return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
}

function hexToRgb(hex: string) {
  const clean = hex.replace('#', '');
  const value = Number.parseInt(clean.length === 3 ? clean.split('').map((char) => `${char}${char}`).join('') : clean, 16);
  return {
    r: (value >> 16) & 255,
    g: (value >> 8) & 255,
    b: value & 255,
  };
}

function rgbToHex(r: number, g: number, b: number) {
  return `#${[r, g, b].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
}
