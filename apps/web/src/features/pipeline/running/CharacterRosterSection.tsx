import { Plus, Trash2 } from 'lucide-react';
import { formatCharacterChapterWindow } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterKind } from './characterBibleArtifact';
import { nextSubjectId } from './characterBibleArtifact';

type Props = { artifact: CharacterBibleArtifact; onChange: (artifact: CharacterBibleArtifact) => void; onSelect: (id: string) => void; readOnly: boolean; selectedId: string };
const GROUPS: Array<{ kind: CharacterKind; label: string }> = [
  { kind: 'protagonist', label: '主角' }, { kind: 'major', label: '重要配角' }, { kind: 'functional', label: '功能角色' }, { kind: 'npc', label: 'NPC' }, { kind: 'historical_record', label: '历史主体' },
];

export function CharacterRosterSection({ artifact, onChange, onSelect, readOnly, selectedId }: Props) {
  const addSubject = (kind: CharacterKind) => {
    const id = nextSubjectId(artifact);
    onChange({ ...artifact, subjects: [...artifact.subjects, { id, name: `未命名主体 ${artifact.subjects.length + 1}`, kind, function: '待明确', drive: '待明确', change: '待明确', debut: 'chapter:1', limits: ['不得超出冻结职责'], demand_refs: ['demand-pending'] }] });
    onSelect(id);
  };
  const removeSubject = (id: string) => {
    const remaining = artifact.subjects.filter((item) => item.id !== id);
    onChange({ ...artifact, subjects: remaining, relations: artifact.relations.filter((item) => item.a !== id && item.b !== id) });
    if (selectedId === id) onSelect(remaining[0]?.id ?? '');
  };
  return <aside className="character-roster-rail"><header><span>主体台账</span><strong>{artifact.subjects.length} 名</strong></header><div className="character-tier-groups">{GROUPS.map((group) => {
    const subjects = artifact.subjects.filter((item) => item.kind === group.kind);
    return <section className="character-tier-group" key={group.kind}><div className="character-tier-heading"><strong>{group.label}</strong><span>{subjects.length}</span>{!readOnly ? <button aria-label={`新增${group.label}`} onClick={() => addSubject(group.kind)} title={`新增${group.label}`} type="button"><Plus size={15} /></button> : null}</div><div className="character-roster-list">{subjects.map((subject) => <div className={`character-roster-item${selectedId === subject.id ? ' active' : ''}`} key={subject.id}><button aria-pressed={selectedId === subject.id} onClick={() => onSelect(subject.id)} type="button"><strong>{subject.name}</strong><span>{subject.function}</span><small>{formatCharacterChapterWindow(subject.debut)}</small></button>{!readOnly && artifact.subjects.length > 1 ? <button aria-label={`删除${subject.name}`} className="character-roster-delete" onClick={() => removeSubject(subject.id)} title="删除主体及其关系" type="button"><Trash2 size={14} /></button> : null}</div>)}{!subjects.length ? <p className="character-tier-empty">尚未编排</p> : null}</div></section>;
  })}</div></aside>;
}
