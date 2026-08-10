import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { Edit3, Maximize2, Network, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { createPortal } from 'react-dom';
import { drawCharacterNode, drawRelationLayer, getCssVar, graphFitPadding, idForEndpoint, linkKey, nameFor } from './characterGraphCanvas';
import { tierNodeValue, tierRingLayout, unaffiliatedColor } from './characterGraphData';
import type { GraphLink, GraphNode } from './characterGraphTypes';
import type { CharacterGraph, CharacterNode, QualityMode, RunEvent } from '../../contracts';
import { ButtonLoadingIndicator } from '../../layout/ButtonLoadingIndicator';
import { backdropMotionVariants, dialogMotionVariants } from '../../lib/motion';
import { qualityModeColors } from '../../lib/qualityModes';
import { useOverlayDialog } from '../../state/useOverlayDialog';
import { CharacterNetworkPanoramaDialog } from './CharacterNetworkPanoramaDialog';
import { characterGraphViewport } from './characterGraphViewport';

type Props = {
  events: RunEvent[];
  artifactStatus?: 'draft' | 'confirmed';
  graphOverride?: CharacterGraph;
  onEdit?: () => void;
  qualityMode?: QualityMode;
  surface?: 'embedded' | 'bare';
  stageEnrichment?: { label: string; detail: string };
};

export function CharacterForceGraphPanel({ artifactStatus, events, onEdit, qualityMode = 'balanced', stageEnrichment, graphOverride, surface = 'embedded' }: Props) {
  const graphRef = useRef<ForceGraphMethods>();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const hoveredNodeRef = useRef<string | null>(null);
  const hoveredLinkRef = useRef<string | null>(null);
  const [hovered, setHovered] = useState<string>('拖拽节点查看人物关系');
  const [selected, setSelected] = useState<CharacterNode | null>(null);
  const [panoramaOpen, setPanoramaOpen] = useState(false);
  const [graphSize, setGraphSize] = useState({ width: 300, height: 240 });
  const graph = graphOverride ?? { nodes: [], edges: [], updated_by: '' };
  const graphKey = useMemo(() => characterGraphSignature(graph), [graph]);
  const generating = events.some((event) => event.stage_id === 'characters' && event.type === 'node.started')
    && !events.some((event) => event.stage_id === 'characters' && event.type === 'artifact.committed');

  const graphData = useMemo<{ nodes: GraphNode[]; links: GraphLink[] }>(() => {
    const positions = tierRingLayout(graph.nodes);
    return {
      nodes: graph.nodes.map((node, index) => ({
        ...node,
        ...positions[index],
        val: tierNodeValue(node),
        color: node.faction?.trim() ? qualityModeColors[qualityMode].accentStrong : unaffiliatedColor,
      })),
      links: graph.edges.map((edge) => ({ ...edge })),
    };
  }, [graphKey, qualityMode]);
  const factionless = graph.nodes.length > 0 && graph.nodes.every((node) => !node.faction?.trim());

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const nextSize = characterGraphViewport({
        containerHeight: entry.contentRect.height,
        containerWidth: entry.contentRect.width,
        viewportHeight: window.innerHeight,
        viewportWidth: window.innerWidth,
      });
      setGraphSize((current) => (
        current.width === nextSize.width && current.height === nextSize.height ? current : nextSize
      ));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const graphApi = graphRef.current;
    if (!graphApi) return;
    graphApi.d3Force('charge')?.strength?.(-360);
    graphApi.d3Force('link')?.distance?.(186);
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
  }, [graphKey, graphSize.height, graphSize.width]);

  return (
    <section className={`insight-card character-card ${surface === 'bare' ? 'bare-surface' : ''}`}>
      <div className="insight-card-head">
        <div>
          <p className="eyebrow">人物脉络</p>
          <h3><Network size={16} />人物关系网</h3>
        </div>
        <div className="rail-metrics">
          {artifactStatus ? <span>{artifactStatus === 'draft' ? '当前稿预览' : '已定稿'}</span> : null}
          <span>{graph.nodes.length} 人物</span>
          <span>{graph.edges.length} 关系</span>
          {factionless ? <span>未标注阵营</span> : null}
          {onEdit ? (
            <button aria-label="编辑人物关系" className="insight-edit-button" onClick={onEdit} title="编辑人物关系" type="button">
              <Edit3 size={14} />
            </button>
          ) : null}
          {graph.nodes.length ? (
            <button aria-label="打开人物关系 3D 全景" className="insight-edit-button" onClick={() => setPanoramaOpen(true)} title="打开 3D 全景" type="button">
              <Maximize2 size={14} />
            </button>
          ) : null}
        </div>
      </div>
      <div className="force-graph-wrap interactive-graph-wrap" ref={wrapRef}>
        {stageEnrichment ? (
          <div className="insight-stage-enrichment character">
            <strong>{stageEnrichment.label}</strong>
            <span>{stageEnrichment.detail}</span>
          </div>
        ) : null}
        {generating ? (
          <div className="graph-generating-badge syncing">
            <ButtonLoadingIndicator />
            正在同步人物关系
          </div>
        ) : null}
        {graph.nodes.length ? <div className="graph-hover-float">{hovered}</div> : null}
        {graph.nodes.length ? <ForceGraph2D
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
          linkDirectionalParticleSpeed={(link) => 0.004 + Number((link as GraphLink).strength ?? 0.5) * 0.004}
          linkWidth={(link) => 0.65 + Number((link as GraphLink).strength ?? 0.5) * 1.05}
          linkColor={(link) => linkKey(link as GraphLink) === hoveredLinkRef.current ? getCssVar('--accent-2') : getCssVar('--edge')}
          autoPauseRedraw
          linkCanvasObjectMode={() => 'after'}
          linkCanvasObject={(link, ctx, globalScale) => drawRelationLayer(link as GraphLink, ctx, globalScale, linkKey(link as GraphLink) === hoveredLinkRef.current)}
          nodeCanvasObject={(node, ctx, globalScale) => drawCharacterNode(node as GraphNode, ctx, globalScale, hoveredNodeRef.current === (node as GraphNode).id)}
          nodePointerAreaPaint={(node, color, ctx) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, 10, 0, 2 * Math.PI, false);
            ctx.fill();
          }}
          onEngineStop={() => {
            graphRef.current?.zoomToFit?.(320, graphFitPadding(graphSize.width, graphSize.height));
          }}
          onNodeHover={(node) => {
            hoveredNodeRef.current = node ? (node as GraphNode).id : null;
            setHovered(node ? `${(node as GraphNode).name} · ${(node as GraphNode).role}` : '拖拽节点查看人物关系');
          }}
          onLinkHover={(link) => {
            hoveredLinkRef.current = link ? linkKey(link as GraphLink) : null;
            setHovered(link ? `${nameFor(graph, idForEndpoint((link as GraphLink).source))} → ${nameFor(graph, idForEndpoint((link as GraphLink).target))} · ${(link as GraphLink).relation}` : '拖拽节点查看人物关系');
          }}
          onNodeClick={(node) => {
            setSelected(node as GraphNode);
          }}
        /> : <div className="runtime-widget-empty">人物基线尚未建立：等待人物档案写入后展示真实关系网，不使用演示数据补位。</div>}
      </div>
      <AnimatePresence>
        {selected ? <CharacterRelationModal graph={graph} mode={qualityMode} node={selected} onClose={() => setSelected(null)} /> : null}
        {panoramaOpen ? <CharacterNetworkPanoramaDialog graph={graph} mode={qualityMode} onClose={() => setPanoramaOpen(false)} /> : null}
      </AnimatePresence>
    </section>
  );
}

function characterGraphSignature(graph: CharacterGraph) {
  return JSON.stringify({
    nodes: graph.nodes.map((node) => [node.id, node.name, node.role, node.faction, node.status, node.tier ?? '']),
    edges: graph.edges.map((edge) => [edge.source, edge.target, edge.relation, edge.strength, edge.kind ?? '', edge.polarity ?? '', edge.history?.length ?? 0]),
  });
}

function CharacterRelationModal({ graph, mode, node, onClose }: { graph: CharacterGraph; mode: QualityMode; node: CharacterNode; onClose: () => void }) {
  const relations = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  return createPortal(
    <motion.div
      animate="animate"
      className={`character-modal-backdrop app-overlay-backdrop runtime-character-detail-backdrop mode-${mode}`}
      exit="exit"
      initial="initial"
      onClick={onClose}
      variants={backdropMotionVariants}
    >
      <motion.article
        animate="animate"
        aria-label={`${node.name}人物关系详情`}
        aria-modal="true"
        className={`character-modal app-dialog-surface runtime-character-detail mode-${mode}`}
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <button aria-label="关闭人物关系详情" className="modal-close" onClick={onClose} title="关闭"><X size={22} /></button>
        <p className="eyebrow">关系详情</p>
        <h3>{node.name}</h3>
        <div className="modal-meta">
          <span>{node.role}</span>
          <span>{node.faction?.trim() || '未标注阵营'}</span>
          <span>{node.status}</span>
        </div>
        <div className="relation-list">
          {relations.length ? relations.map((edge) => {
            const otherId = edge.source === node.id ? edge.target : edge.source;
            return (
              <section key={`${edge.source}-${edge.target}`}>
                <strong>{node.name} → {nameFor(graph, String(otherId))}</strong>
                <span>{edge.relation} · 强度 {Math.round(edge.strength * 100)}%</span>
              </section>
            );
          }) : (
            <section>
              <strong>暂无已确认关系</strong>
              <span>后续阶段写回人物关系后，会在这里展示该人物的新增连接。</span>
            </section>
          )}
        </div>
      </motion.article>
    </motion.div>,
    document.body,
  );
}
