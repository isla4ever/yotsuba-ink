import { useMemo } from 'react';
import type { CharacterRecommendation, InfoRecommendation } from './infoRecommendationModel';
import { CharacterRelationEditor, relationSummaryFor } from './CharacterRelationEditor';

type Props = {
  activeIndex: number;
  character: CharacterRecommendation;
  characters: CharacterRecommendation[];
  readOnly: boolean;
  relationships: InfoRecommendation['relationships'];
  onChange: (patch: Partial<CharacterRecommendation>) => void;
  onRelationshipsChange: (relationships: InfoRecommendation['relationships']) => void;
};

export function InfoCharacterEditor({
  activeIndex,
  character,
  characters,
  onChange,
  onRelationshipsChange,
  readOnly,
  relationships,
}: Props) {
  const relationChips = useMemo(
    () => relationSummaryFor(character.name, relationships)
      .split(/[；;]/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 5),
    [character.name, relationships],
  );

  return (
    <article className="character-dossier-card">
      <div className="character-dossier-scroll">
        <div className="character-dossier-cover">
          <span>{avatarFor(character.name)}</span>
          <div>
            <div className="character-dossier-basics">
              <label>
                <small>人物姓名</small>
                <input readOnly={readOnly} value={character.name} onChange={(event) => onChange({ name: event.target.value })} placeholder="例如：林澈" />
              </label>
              <label>
                <small>身份定位</small>
                <input readOnly={readOnly} value={character.identity} onChange={(event) => onChange({ identity: event.target.value })} placeholder="例如：小镇诊所里守着秘密的年轻医生" />
              </label>
            </div>
            {relationChips.length ? (
              <div className="dossier-relation-chips">
                {relationChips.map((chip) => <b key={chip}>{chip}</b>)}
              </div>
            ) : null}
          </div>
        </div>
        <div className="character-dossier-notes">
          <label className="dossier-long-field">
            <span>背景档案</span>
            <small>人物旧事与主线的隐性联系</small>
            <textarea readOnly={readOnly} value={character.background} onChange={(event) => onChange({ background: event.target.value })} />
          </label>
          <label className="dossier-long-field">
            <span>行动动机</span>
            <small>行动目标与失去代价</small>
            <textarea readOnly={readOnly} value={character.motivation} onChange={(event) => onChange({ motivation: event.target.value })} />
          </label>
          <label className="dossier-long-field">
            <span>成长方向</span>
            <small>主线推进中的变化与最终选择</small>
            <textarea readOnly={readOnly} value={character.growth_direction} onChange={(event) => onChange({ growth_direction: event.target.value })} />
          </label>
        </div>
      </div>
      <CharacterRelationEditor
        activeCharacter={character}
        activeIndex={activeIndex}
        characters={characters}
        readOnly={readOnly}
        onRelationshipsChange={onRelationshipsChange}
        relationships={relationships}
      />
    </article>
  );
}

export function avatarFor(name: string) {
  return name.trim().slice(0, 1) || '人';
}
