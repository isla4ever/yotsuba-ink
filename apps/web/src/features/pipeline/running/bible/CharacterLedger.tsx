import { appearanceLabel, nodeColor, relationSemantics, tierLabels } from './characterNetworkModel';
import { nodeTier } from '../characterGraphSemantics';
import type { CharacterGraph } from '../../contracts';

type Props = {
  graph: CharacterGraph;
  selectedId: string;
  onSelect: (nodeId: string) => void;
};

/**
 * Keyboard-reachable equivalent of the canvas network (the canvas has an empty
 * accessibility tree). Shares the same selection state as the graph view.
 */
export function CharacterLedger({ graph, onSelect, selectedId }: Props) {
  const nameFor = (id: string) => graph.nodes.find((node) => node.id === id)?.name ?? id;
  return (
    <div className="bible-character-ledger">
      <section aria-label="人物清单">
        <h3>人物（{graph.nodes.length}）</h3>
        <ul className="bible-ledger-list">
          {graph.nodes.map((node) => {
            const active = node.id === selectedId;
            const appearance = appearanceLabel(node);
            return (
              <li key={node.id}>
                <button
                  aria-pressed={active}
                  className={`bible-ledger-row${active ? ' active' : ''}`}
                  onClick={() => onSelect(active ? '' : node.id)}
                  type="button"
                >
                  <span aria-hidden="true" className="bible-ledger-dot" style={{ background: nodeColor(node) }} />
                  <span className="bible-ledger-name">{node.name}</span>
                  <span className="bible-ledger-meta">
                    {tierLabels[nodeTier(node)]}
                    {node.faction?.trim() ? ` · ${node.faction}` : ' · 未标注阵营'}
                    {appearance ? ` · ${appearance}` : ''}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section aria-label="关系清单">
        <h3>关系（{graph.edges.length}）</h3>
        {graph.edges.length ? (
          <ul className="bible-ledger-list">
            {graph.edges.map((edge, index) => (
              <li key={`${edge.source}-${edge.target}-${edge.relation}-${index}`}>
                <button
                  className={`bible-ledger-row${edge.source === selectedId || edge.target === selectedId ? ' related' : ''}`}
                  onClick={() => onSelect(edge.source)}
                  type="button"
                >
                  <span className="bible-ledger-name">{nameFor(edge.source)} → {nameFor(edge.target)}</span>
                  <span className="bible-ledger-meta">{edge.relation} · {relationSemantics(edge)}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="bible-empty-note">当前视图内没有关系连线。</p>
        )}
      </section>
    </div>
  );
}
