import { Focus, ZoomIn, ZoomOut } from 'lucide-react';
import { lazy, Suspense, useMemo, useState } from 'react';
import { CharacterLedger } from './CharacterLedger';
import { CharacterNetworkView } from './CharacterNetworkView';
import { CharacterProfilePanel } from './CharacterProfilePanel';
import { NetworkTimeline } from './NetworkTimeline';
import {
  currentTickId,
  factionLegendEntries,
  filterGraphByTiers,
  graphAtTimelineTick,
  hasMissingTimelineMarkers,
  networkTimelineTicks,
  nodeInFaction,
  stanceLabels,
  tierLabels,
  tiersPresent,
  timelineViewpointLabel,
  toggleFactionHighlight,
} from './characterNetworkModel';
import { bibleCharacterGraph } from './storyBibleModel';
import type { CharacterNode, CharacterTier, RunEvent, WorkflowDefinition } from '../../contracts';
import { qualityModeColors } from '../../lib/qualityModes';

type Props = {
  events: RunEvent[];
  workflow: WorkflowDefinition;
};

/** The 3D stack (react-force-graph-3d + three) loads only when the user enters panorama mode. */
const CharacterNetwork3DView = lazy(() =>
  import('./CharacterNetwork3DView').then((module) => ({ default: module.CharacterNetwork3DView })),
);

const sourceNotes = {
  committed: '数据来源：各阶段定稿写回的人物图谱。',
  derived: '数据来源：阶段产物预览（尚未有写回图谱）。',
} as const;

type ViewMode = 'graph' | 'ledger' | 'space';
type CameraRequest = { id: string; key: number; kind: 'fit' | 'focus' | 'zoom-in' | 'zoom-out' };

export function CharactersSection({ events, workflow }: Props) {
  const [hiddenTiers, setHiddenTiers] = useState<ReadonlySet<CharacterTier>>(new Set());
  const [highlightedFaction, setHighlightedFaction] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [view, setView] = useState<ViewMode>('graph');
  const [tickId, setTickId] = useState(currentTickId);
  const [cameraRequest, setCameraRequest] = useState<CameraRequest>();

  const { graph, source } = useMemo(() => bibleCharacterGraph(events, workflow), [events, workflow]);
  const ticks = useMemo(() => networkTimelineTicks(graph), [graph]);
  const degraded = useMemo(() => hasMissingTimelineMarkers(graph), [graph]);
  const activeTickId = ticks.some((tick) => tick.id === tickId) ? tickId : currentTickId;
  const timeGraph = useMemo(() => graphAtTimelineTick(graph, ticks, activeTickId), [graph, ticks, activeTickId]);
  const visibleGraph = useMemo(() => filterGraphByTiers(timeGraph, hiddenTiers), [timeGraph, hiddenTiers]);
  const tiers = tiersPresent(graph);
  const legend = factionLegendEntries(visibleGraph);
  const highlightEntry = legend.find((entry) => entry.id === highlightedFaction) ?? null;
  const viewpoint = timelineViewpointLabel(ticks.find((tick) => tick.id === activeTickId));
  const accentColor = qualityModeColors[workflow.quality_mode].accentStrong;

  if (source === 'empty') {
    return (
      <section className="bible-section bible-section-empty">
        <p className="bible-empty-note">人物基线尚未建立——在创作立项阶段生成人物档案与关系后，这里会展示全书人物关系网。</p>
      </section>
    );
  }

  const toggleTier = (tier: CharacterTier) => {
    setHiddenTiers((current) => {
      const next = new Set(current);
      if (next.has(tier)) next.delete(tier);
      else next.add(tier);
      return next;
    });
  };

  const isNodeDimmed = (node: Pick<CharacterNode, 'faction' | 'faction_id'>) =>
    Boolean(highlightEntry && !nodeInFaction(node, highlightEntry));

  const selectNode = (nodeId: string) => {
    setSelectedId(nodeId);
    if (nodeId) {
      setCameraRequest((current) => ({ id: nodeId, key: (current?.key ?? 0) + 1, kind: 'focus' }));
    } else {
      setCameraRequest(undefined);
    }
  };

  const requestCamera = (kind: CameraRequest['kind']) => {
    setCameraRequest((current) => ({ id: selectedId, key: (current?.key ?? 0) + 1, kind }));
  };

  return (
    <section className="bible-section bible-characters">
      <div className="bible-characters-toolbar">
        <div aria-label="视图切换" className="bible-view-toggle" role="group">
          <button aria-pressed={view === 'graph'} className={view === 'graph' ? 'active' : ''} onClick={() => setView('graph')} type="button">关系网大图</button>
          <button aria-pressed={view === 'ledger'} className={view === 'ledger' ? 'active' : ''} onClick={() => setView('ledger')} type="button">人物与关系清单</button>
          <button aria-pressed={view === 'space'} className={view === 'space' ? 'active' : ''} onClick={() => setView('space')} type="button">3D 全景</button>
        </div>
        <div aria-label="按层级过滤" className="bible-tier-filters" role="group">
          {tiers.map((tier) => {
            const visible = !hiddenTiers.has(tier);
            return (
              <button aria-pressed={visible} className={`bible-filter-chip${visible ? ' active' : ''}`} key={tier} onClick={() => toggleTier(tier)} type="button">
                {tierLabels[tier]}
              </button>
            );
          })}
        </div>
        <span className="bible-toolbar-count">{visibleGraph.nodes.length} 人物 · {visibleGraph.edges.length} 关系</span>
      </div>
      {legend.length ? (
        <div aria-label="阵营图例" className="bible-faction-legend" role="group">
          {legend.map((entry) => (
            <button
              aria-pressed={entry.id === highlightedFaction}
              className={`bible-legend-chip${entry.id === highlightedFaction ? ' active' : ''}`}
              key={entry.id}
              onClick={() => setHighlightedFaction((current) => toggleFactionHighlight(current, entry.id))}
              title="点击高亮该阵营节点"
              type="button"
            >
              <span aria-hidden="true" className="bible-legend-swatch" style={{ background: accentColor }} />
              <span>{entry.name}</span>
              {entry.stance ? <small>{stanceLabels[entry.stance]}</small> : null}
              <small>{entry.memberCount} 人</small>
            </button>
          ))}
        </div>
      ) : null}
      <div className={`bible-characters-body${view === 'space' ? ' bible-characters-body-3d' : ''}`}>
        {view === 'graph' ? (
          <CharacterNetworkView
            accentColor={accentColor}
            graph={visibleGraph}
            isNodeDimmed={isNodeDimmed}
            onSelectNode={selectNode}
            selectedId={selectedId}
          />
        ) : null}
        {view === 'ledger' ? <CharacterLedger graph={visibleGraph} onSelect={selectNode} selectedId={selectedId} /> : null}
        {view === 'space' ? (
          <div className="bible-network-3d-stage">
            <div className="bible-network-3d-bar">
              <span className="bible-network-3d-hint">浏览模式：拖动旋转 · 滚轮缩放 · 点击节点同步选中档案；编辑请返回 2D。</span>
              <div className="bible-network-3d-actions">
                <div aria-label="3D 视图控制" className="bible-network-3d-controls" role="group">
                  <button aria-label="缩小关系网" onClick={() => requestCamera('zoom-out')} title="缩小" type="button"><ZoomOut size={14} /></button>
                  <button aria-label="适配全景" onClick={() => requestCamera('fit')} title="适配全景" type="button"><Focus size={14} /></button>
                  <button aria-label="放大关系网" onClick={() => requestCamera('zoom-in')} title="放大" type="button"><ZoomIn size={14} /></button>
                </div>
                <button className="bible-network-3d-exit" onClick={() => setView('graph')} type="button">返回 2D</button>
              </div>
            </div>
            <Suspense fallback={<p className="bible-network-3d-loading">正在加载 3D 全景模块…</p>}>
              <CharacterNetwork3DView
                accentColor={accentColor}
                cameraRequest={cameraRequest}
                graph={visibleGraph}
                isNodeDimmed={isNodeDimmed}
                onSelectNode={selectNode}
                selectedId={selectedId}
              />
            </Suspense>
          </div>
        ) : null}
        <CharacterProfilePanel graph={timeGraph} onSelect={selectNode} selectedId={selectedId} viewpoint={viewpoint} />
      </div>
      <NetworkTimeline activeId={activeTickId} degraded={degraded} onSelect={setTickId} ticks={ticks} />
      <p className="bible-source-note">{sourceNotes[source]}</p>
    </section>
  );
}
