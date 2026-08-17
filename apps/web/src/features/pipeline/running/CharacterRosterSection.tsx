import { formatCharacterChapterWindow } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterKind } from './characterBibleArtifact';

type Props = { artifact: CharacterBibleArtifact; onSelect: (id: string) => void; selectedId: string };
const GROUPS: Array<{ kind: CharacterKind; label: string }> = [
  { kind: 'protagonist', label: '主角' }, { kind: 'major', label: '重要配角' }, { kind: 'functional', label: '功能角色' }, { kind: 'npc', label: 'NPC' }, { kind: 'historical_record', label: '历史主体' },
];

export function CharacterRosterSection({ artifact, onSelect, selectedId }: Props) {
  return <aside className="character-roster-rail"><header><span>主体台账</span><strong>{artifact.subjects.length} 名</strong></header><div className="character-tier-groups">{GROUPS.map((group) => {
    const subjects = artifact.subjects.filter((item) => item.kind === group.kind);
    return <section className="character-tier-group" key={group.kind}><div className="character-tier-heading"><strong>{group.label}</strong><span>{subjects.length}</span></div><div className="character-roster-list">{subjects.map((subject) => <div className={`character-roster-item${selectedId === subject.id ? ' active' : ''}`} key={subject.id}><button aria-pressed={selectedId === subject.id} onClick={() => onSelect(subject.id)} type="button"><strong>{subject.name}</strong><span>{subject.function}</span><small>{formatCharacterChapterWindow(subject.debut)}</small></button></div>)}{!subjects.length ? <p className="character-tier-empty">尚未编排</p> : null}</div></section>;
  })}</div></aside>;
}
