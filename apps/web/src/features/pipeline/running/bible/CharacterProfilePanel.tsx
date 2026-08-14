import { UserRound } from 'lucide-react';
import {
  appearanceLabel,
  characterProfile,
  kindLabels,
  polarityLabels,
  tierLabels,
} from './characterNetworkModel';
import type { CharacterGraph } from '../../contracts';

type Props = {
  graph: CharacterGraph;
  selectedId: string;
  onSelect: (nodeId: string) => void;
  /** Timeline viewpoint line, e.g.「视点：第3章」; empty on the current (full) view. */
  viewpoint?: string;
};

/** Read-only character dossier for the node selected in the graph or ledger. */
export function CharacterProfilePanel({ graph, onSelect, selectedId, viewpoint }: Props) {
  const profile = characterProfile(graph, selectedId);
  if (!profile) {
    return (
      <aside aria-label="人物档案" className="bible-profile-panel">
        <p className="eyebrow">人物档案</p>
        {viewpoint ? <p className="bible-profile-viewpoint">{viewpoint}</p> : null}
        <div className="bible-card-empty" role="status">
          <UserRound size={18} />
          <p>尚未选择人物</p>
          <small>点击图中节点或人物清单条目，在这里查看档案与关系明细。</small>
        </div>
      </aside>
    );
  }
  const { node, relations, tier } = profile;
  const appearance = appearanceLabel(node);
  return (
    <aside aria-label={`${node.name}的人物档案`} className="bible-profile-panel">
      <p className="eyebrow">人物档案</p>
      {viewpoint ? <p className="bible-profile-viewpoint">{viewpoint}</p> : null}
      <h3><UserRound size={15} />{node.name}</h3>
      <dl className="bible-profile-facts">
        <div><dt>层级</dt><dd>{tierLabels[tier]}</dd></div>
        <div><dt>阵营</dt><dd>{node.faction?.trim() || '未标注阵营'}</dd></div>
        {node.role.trim() ? <div><dt>角色定位</dt><dd>{node.role}</dd></div> : null}
        {node.status.trim() ? <div><dt>当前状态</dt><dd>{node.status}</dd></div> : null}
        {appearance ? <div><dt>首次出场</dt><dd>{appearance}</dd></div> : null}
      </dl>
      <h4>关系（{relations.length}）</h4>
      {relations.length ? (
        <ul className="bible-profile-relations">
          {relations.map((row) => (
            <li key={row.key}>
              <button className="bible-ledger-row" onClick={() => onSelect(row.otherId)} type="button">
                <span className="bible-ledger-name">
                  {row.direction === 'out' ? `${node.name} → ${row.otherName}` : `${row.otherName} → ${node.name}`}
                </span>
                <span className="bible-ledger-meta">
                  {row.relation}
                  {row.kind ? ` · ${kindLabels[row.kind]}` : ''}
                  {row.polarity ? ` · ${polarityLabels[row.polarity]}` : ''}
                  {` · 强度 ${Math.round(row.strength * 100)}%`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="bible-empty-note">该人物暂无已登记关系；后续阶段写回后会在这里出现。</p>
      )}
    </aside>
  );
}
