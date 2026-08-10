import { Plus, Trash2 } from 'lucide-react';
import { formatCharacterChapterWindow } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterTier } from './characterBibleArtifact';
import { nextCharacterId } from './characterBibleArtifact';

type Props = {
  artifact: CharacterBibleArtifact;
  onChange: (artifact: CharacterBibleArtifact) => void;
  onSelect: (characterId: string) => void;
  readOnly: boolean;
  selectedId: string;
};

const GROUPS: Array<{ tier: CharacterTier; label: string }> = [
  { tier: 'protagonist', label: '主角' },
  { tier: 'major', label: '重要配角' },
  { tier: 'functional', label: '功能角色' },
];

export function CharacterRosterSection({ artifact, onChange, onSelect, readOnly, selectedId }: Props) {
  const addCharacter = (tier: CharacterTier) => {
    const id = nextCharacterId(artifact);
    onChange({
      ...artifact,
      characters: [...artifact.characters, {
        id,
        name: `未命名角色 ${artifact.characters.length + 1}`,
        tier,
        narrative_function: '待明确',
        external_goal: '待明确',
        inner_need: '待明确',
        arc: { start: '待明确', turning_point: '待明确', end: '待明确' },
        first_appearance_window: 'chapter:1',
        hard_boundaries: [],
      }],
    });
    onSelect(id);
  };
  const removeCharacter = (id: string) => {
    const remaining = artifact.characters.filter((character) => character.id !== id);
    onChange({
      ...artifact,
      characters: remaining,
      relationships: artifact.relationships.filter((relationship) => relationship.source_id !== id && relationship.target_id !== id),
    });
    if (selectedId === id) onSelect(remaining[0]?.id ?? '');
  };
  return (
    <aside className="character-roster-rail">
      <header>
        <span>角色台账</span>
        <strong>{artifact.characters.length} 名</strong>
      </header>
      <div className="character-tier-groups">
        {GROUPS.map((group) => {
          const characters = artifact.characters.filter((character) => character.tier === group.tier);
          return (
            <section className="character-tier-group" key={group.tier}>
              <div className="character-tier-heading">
                <strong>{group.label}</strong>
                <span>{characters.length}</span>
                {!readOnly ? (
                  <button aria-label={`新增${group.label}`} onClick={() => addCharacter(group.tier)} title={`新增${group.label}`} type="button">
                    <Plus size={15} />
                  </button>
                ) : null}
              </div>
              <div className="character-roster-list">
                {characters.map((character) => (
                  <div className={`character-roster-item${selectedId === character.id ? ' active' : ''}`} key={character.id}>
                    <button aria-pressed={selectedId === character.id} onClick={() => onSelect(character.id)} type="button">
                      <strong>{character.name}</strong>
                      <span>{character.narrative_function}</span>
                      <small>{formatCharacterChapterWindow(character.first_appearance_window)}</small>
                    </button>
                    {!readOnly && artifact.characters.length > 1 ? (
                      <button aria-label={`删除${character.name}`} className="character-roster-delete" onClick={() => removeCharacter(character.id)} title="删除人物及其关系" type="button">
                        <Trash2 size={14} />
                      </button>
                    ) : null}
                  </div>
                ))}
                {!characters.length ? <p className="character-tier-empty">尚未编排</p> : null}
              </div>
            </section>
          );
        })}
      </div>
    </aside>
  );
}
