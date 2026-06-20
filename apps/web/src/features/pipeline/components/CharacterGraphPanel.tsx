import { Network } from 'lucide-react';
import type { CharacterGraph, RunEvent } from '../types/workflow';

type Props = {
  events: RunEvent[];
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

export function CharacterGraphPanel({ events }: Props) {
  const latest = events.find((event) => event.type === 'character_graph_updated' && event.character_graph);
  const graph = latest?.character_graph ?? fallback;
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><Network size={16} />人物关系网</h3>
        <div className="relation-map">
          {graph.edges.map((edge, index) => <i key={`${edge.source}-${edge.target}-${index}`} style={{ width: `${80 + edge.strength * 80}px` }} />)}
          {graph.nodes.map((node, index) => (
            <div className={`character-dot p${index + 1}`} key={node.id}>
              <strong>{node.name}</strong>
              <span>{node.role}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="config-section">
        <h3>人物网格栏</h3>
        <div className="character-grid">
          {graph.nodes.map((node) => (
            <article key={node.id}>
              <strong>{node.name}</strong>
              <span>{node.role} · {node.faction}</span>
              <small>{node.status}</small>
            </article>
          ))}
        </div>
      </section>
      <section className="config-section">
        <h3>关系边</h3>
        <div className="field-list">
          {graph.edges.map((edge) => (
            <article key={`${edge.source}-${edge.target}`}>
              <strong>{nameFor(graph, edge.source)} → {nameFor(graph, edge.target)}</strong>
              <span>{edge.relation} · 强度 {Math.round(edge.strength * 100)}%</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function nameFor(graph: CharacterGraph, id: string) {
  return graph.nodes.find((node) => node.id === id)?.name ?? id;
}
