import { formatCharacterChapterWindow } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterKind } from './characterBibleArtifact';
import { CharacterKindIcon, characterKindLabels } from './CharacterKindIcon';

type Props = { artifact: CharacterBibleArtifact; onSelect: (id: string) => void; selectedId: string };
const GROUPS: Array<{ kind: CharacterKind; label: string }> = [
  'protagonist', 'major', 'functional', 'npc', 'historical_record',
].map((kind) => ({ kind: kind as CharacterKind, label: characterKindLabels[kind as CharacterKind] }));

export function CharacterRosterSection({ artifact, onSelect, selectedId }: Props) {
  return <aside className="character-roster-rail"><header><span>主体台账</span><strong>{artifact.subjects.length} 名</strong></header><div className="character-tier-groups">{GROUPS.map((group) => {
    const subjects = artifact.subjects.filter((item) => item.kind === group.kind);
    return <section className="character-tier-group" key={group.kind}><div className="character-tier-heading"><CharacterKindIcon kind={group.kind} /><strong>{group.label}</strong><span>{subjects.length}</span></div><div className="character-roster-list">{subjects.map((subject) => <div className={`character-roster-item${selectedId === subject.id ? ' active' : ''}`} key={subject.id}><button aria-pressed={selectedId === subject.id} onClick={() => onSelect(subject.id)} type="button"><span className="character-roster-name"><CharacterKindIcon kind={subject.kind} /><strong>{subject.name}</strong></span><span>{subject.function}</span><small>{formatCharacterChapterWindow(subject.debut)}</small></button></div>)}{!subjects.length ? <p className="character-tier-empty">尚未编排</p> : null}</div></section>;
  })}</div></aside>;
}
