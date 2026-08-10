import { ArrowRight, CircleDot, Route, UsersRound } from 'lucide-react';
import { formatCharacterChapterWindow, parseChapterWindow } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterRecord } from './characterBibleArtifact';

type Props = {
  artifact: CharacterBibleArtifact;
  character: CharacterRecord;
  onSelect: (characterId: string) => void;
};

export function CharacterOrchestrationPanel({ artifact, character, onSelect }: Props) {
  const related = artifact.relationships.flatMap((relationship) => {
    if (relationship.source_id !== character.id && relationship.target_id !== character.id) return [];
    const otherId = relationship.source_id === character.id ? relationship.target_id : relationship.source_id;
    const other = artifact.characters.find((item) => item.id === otherId);
    return other ? [{ relationship, other }] : [];
  });
  const timeline = [
    ...artifact.characters.map((item) => ({ id: item.id, label: item.name, kind: 'character', start: parseChapterWindow(item.first_appearance_window).start, window: item.first_appearance_window })),
    ...artifact.npc_slots.map((item) => ({ id: item.id, label: item.function, kind: 'npc', start: parseChapterWindow(item.first_appearance_window).start, window: item.first_appearance_window })),
  ].sort((left, right) => left.start - right.start || left.label.localeCompare(right.label, 'zh-CN'));
  const protagonistCount = artifact.characters.filter((item) => item.tier === 'protagonist').length;
  const majorCount = artifact.characters.filter((item) => item.tier === 'major').length;
  return (
    <aside className="character-orchestration-panel">
      <section className="character-coverage">
        <header><UsersRound size={15} /><strong>职责覆盖</strong></header>
        <dl>
          <div><dt>主角</dt><dd className={protagonistCount ? 'ready' : 'missing'}>{protagonistCount}</dd></div>
          <div><dt>重要配角</dt><dd>{majorCount}</dd></div>
          <div><dt>功能角色</dt><dd>{artifact.characters.length - protagonistCount - majorCount}</dd></div>
          <div><dt>NPC 槽位</dt><dd>{artifact.npc_slots.length}</dd></div>
        </dl>
      </section>
      <section className="character-neighborhood">
        <header><Route size={15} /><div><span>关系邻域</span><strong>{character.name}</strong></div></header>
        <div className="character-neighborhood-list">
          {related.map(({ other, relationship }, index) => (
            <button key={`${relationship.source_id}-${relationship.target_id}-${index}`} onClick={() => onSelect(other.id)} type="button">
              <span>{relationship.nature}</span>
              <strong>{other.name}</strong>
              <small>{relationship.pressure}</small>
              <ArrowRight size={14} />
            </button>
          ))}
          {!related.length ? <p>尚未为该角色建立关系边</p> : null}
        </div>
      </section>
      <section className="character-appearance-timeline">
        <header><CircleDot size={15} /><strong>首次出现窗口</strong></header>
        <div className="character-timeline-list">
          {timeline.map((item) => (
            <div className={item.id === character.id ? 'active' : ''} key={item.id}>
              <span>{formatCharacterChapterWindow(item.window)}</span>
              <i />
              <strong>{item.label}</strong>
              <small>{item.kind === 'npc' ? 'NPC' : '角色'}</small>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
