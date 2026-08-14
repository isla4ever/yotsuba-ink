import { ArrowRight, CircleDot, Route, UsersRound } from 'lucide-react';
import { formatCharacterChapterWindow, parseChapterWindow } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterSubject } from './characterBibleArtifact';

type Props = { artifact: CharacterBibleArtifact; subject: CharacterSubject; onSelect: (id: string) => void };

export function CharacterOrchestrationPanel({ artifact, subject, onSelect }: Props) {
  const related = artifact.relations.flatMap((relation) => {
    if (relation.a !== subject.id && relation.b !== subject.id) return [];
    const other = artifact.subjects.find((item) => item.id === (relation.a === subject.id ? relation.b : relation.a));
    return other ? [{ relation, other }] : [];
  });
  const timeline = artifact.subjects.map((item) => ({ ...item, start: parseChapterWindow(item.debut).start })).sort((left, right) => left.start - right.start || left.name.localeCompare(right.name, 'zh-CN'));
  const count = (kind: CharacterSubject['kind']) => artifact.subjects.filter((item) => item.kind === kind).length;
  return <aside className="character-orchestration-panel"><section className="character-coverage"><header><UsersRound size={15} /><strong>职责覆盖</strong></header><dl><div><dt>主角</dt><dd className={count('protagonist') ? 'ready' : 'missing'}>{count('protagonist')}</dd></div><div><dt>重要配角</dt><dd>{count('major')}</dd></div><div><dt>功能角色</dt><dd>{count('functional')}</dd></div><div><dt>NPC</dt><dd>{count('npc')}</dd></div></dl></section><section className="character-neighborhood"><header><Route size={15} /><div><span>关系邻域</span><strong>{subject.name}</strong></div></header><div className="character-neighborhood-list">{related.map(({ other, relation }, index) => <button key={`${relation.a}-${relation.b}-${index}`} onClick={() => onSelect(other.id)} type="button"><span>{relation.type}</span><strong>{other.name}</strong><small>{relation.pressure}</small><ArrowRight size={14} /></button>)}{!related.length ? <p>尚未为该主体建立关系边</p> : null}</div></section><section className="character-appearance-timeline"><header><CircleDot size={15} /><strong>首次出现窗口</strong></header><div className="character-timeline-list">{timeline.map((item) => <div className={item.id === subject.id ? 'active' : ''} key={item.id}><span>{formatCharacterChapterWindow(item.debut)}</span><i /><strong>{item.name}</strong><small>{kindLabel(item.kind)}</small></div>)}</div></section></aside>;
}

function kindLabel(kind: CharacterSubject['kind']) { return kind === 'historical_record' ? '历史主体' : kind === 'npc' ? 'NPC' : kind === 'functional' ? '功能角色' : kind === 'major' ? '重要配角' : '主角'; }
