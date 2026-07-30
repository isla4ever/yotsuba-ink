import { Eye, PenLine, Users } from 'lucide-react';
import type { InfoRecommendation } from './infoRecommendationModel';

type Props = {
  onEdit: () => void;
  readOnly: boolean;
  recommendation: InfoRecommendation;
};

export function InfoCharacterRoster({ onEdit, readOnly, recommendation }: Props) {
  return (
    <section className="info-character-roster">
      <header>
        <span><Users size={15} />人物档案</span>
        <b>{recommendation.characters.length} 人 · {recommendation.relationships.length} 组关系</b>
        <button aria-label={readOnly ? '预览人物档案' : '编辑人物档案'} className="square-action-button" onClick={onEdit} type="button">
          {readOnly ? <Eye size={14} /> : <PenLine size={14} />}
        </button>
      </header>
      <div className="info-character-ledger">
        {recommendation.characters.map((character, index) => (
          <button key={`${character.name}-${index}`} onClick={onEdit} type="button">
            <i>{character.name.trim().slice(0, 1) || '人'}</i>
            <span>
              <strong>{character.name || `角色 ${index + 1}`}</strong>
              <small>{character.identity || '身份待补充'}</small>
            </span>
            <em>{character.motivation || '动机待补充'}</em>
            <b>{relationCount(character.name, recommendation)} 关系</b>
          </button>
        ))}
        {!recommendation.characters.length ? (
          <button className="empty" onClick={onEdit} type="button">
            <Users size={15} /><span><strong>人物档案待补充</strong><small>至少需要一名可进入后续阶段的人物</small></span>
          </button>
        ) : null}
      </div>
    </section>
  );
}

function relationCount(name: string, recommendation: InfoRecommendation) {
  return recommendation.relationships.filter((edge) => edge.source === name || edge.target === name).length;
}
