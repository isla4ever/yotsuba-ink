import { Plus, Trash2 } from 'lucide-react';
import type { CharacterBibleArtifact, CharacterRelationship } from './characterBibleArtifact';

type Props = {
  artifact: CharacterBibleArtifact;
  onChange: (artifact: CharacterBibleArtifact) => void;
  readOnly: boolean;
};

export function CharacterRelationshipSection({ artifact, onChange, readOnly }: Props) {
  const updateRelationship = (index: number, patch: Partial<CharacterRelationship>) => {
    onChange({
      ...artifact,
      relationships: artifact.relationships.map((relationship, itemIndex) => itemIndex === index ? { ...relationship, ...patch } : relationship),
    });
  };
  const addRelationship = () => {
    const source = artifact.characters[0]?.id ?? '';
    const target = artifact.characters.find((character) => character.id !== source)?.id ?? '';
    onChange({
      ...artifact,
      relationships: [...artifact.relationships, {
        source_id: source,
        target_id: target,
        nature: '待补充',
        initial_state: '待补充',
        pressure: '待补充',
      }],
    });
  };
  return (
    <section className="character-bible-section character-relationship-section">
      <header>
        <div>
          <span>关系矩阵</span>
          <strong>{artifact.relationships.length} 组有效关系</strong>
        </div>
        {!readOnly && artifact.characters.length > 1 ? (
          <button className="character-section-command" onClick={addRelationship} type="button"><Plus size={15} />新增关系</button>
        ) : null}
      </header>
      <div className="character-relationship-table" role="table">
        <div className="character-relationship-head" role="row">
          <span>起点</span><span>终点</span><span>关系性质</span><span>初始状态</span><span>压力源</span><span />
        </div>
        {artifact.relationships.map((relationship, index) => (
          <div className="character-relationship-row" key={`${relationship.source_id}-${relationship.target_id}-${index}`} role="row">
            <CharacterSelect artifact={artifact} onChange={(source_id) => updateRelationship(index, { source_id })} readOnly={readOnly} value={relationship.source_id} />
            <CharacterSelect artifact={artifact} onChange={(target_id) => updateRelationship(index, { target_id })} readOnly={readOnly} value={relationship.target_id} />
            <input aria-label="关系性质" onChange={(event) => updateRelationship(index, { nature: event.target.value })} readOnly={readOnly} value={relationship.nature} />
            <input aria-label="关系初始状态" onChange={(event) => updateRelationship(index, { initial_state: event.target.value })} readOnly={readOnly} value={relationship.initial_state} />
            <input aria-label="关系压力源" onChange={(event) => updateRelationship(index, { pressure: event.target.value })} readOnly={readOnly} value={relationship.pressure} />
            {!readOnly ? (
              <button aria-label="删除关系" onClick={() => onChange({ ...artifact, relationships: artifact.relationships.filter((_, itemIndex) => itemIndex !== index) })} title="删除关系" type="button">
                <Trash2 size={15} />
              </button>
            ) : <span />}
          </div>
        ))}
        {!artifact.relationships.length ? <p className="character-table-empty">当前没有关系边</p> : null}
      </div>
    </section>
  );
}

function CharacterSelect({ artifact, onChange, readOnly, value }: { artifact: CharacterBibleArtifact; onChange: (value: string) => void; readOnly: boolean; value: string }) {
  return (
    <select aria-label="关系人物" disabled={readOnly} onChange={(event) => onChange(event.target.value)} value={value}>
      <option value="">未选择</option>
      {artifact.characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
    </select>
  );
}
