import { GitBranch, List, LockKeyhole, Orbit, UsersRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CharacterDossierEditor } from './CharacterDossierEditor';
import { CharacterOrchestrationPanel } from './CharacterOrchestrationPanel';
import { CharacterRelationshipSection } from './CharacterRelationshipSection';
import { CharacterRosterSection } from './CharacterRosterSection';
import { CharacterStarMapPanel } from './CharacterStarMapPanel';
import { parseCharacterBibleArtifact, type CharacterBibleArtifact } from './characterBibleArtifact';

type Props = {
  onArtifactChange: (artifact: CharacterBibleArtifact) => void;
  readOnly: boolean;
  result: string;
  sourceResult: string;
  totalChapters?: number;
};

export function CharacterStageView({ onArtifactChange, readOnly, result, sourceResult, totalChapters }: Props) {
  const parsed = useMemo(() => parseCharacterBibleArtifact(result), [result]);
  const [artifact, setArtifact] = useState<CharacterBibleArtifact | null>(parsed.artifact);
  const [selectedId, setSelectedId] = useState(parsed.artifact?.subjects[0]?.id ?? '');
  const [view, setView] = useState<'star-map' | 'roster'>(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'roster';
    return window.matchMedia('(max-width: 760px)').matches ? 'roster' : 'star-map';
  });
  useEffect(() => {
    const nextArtifact = parseCharacterBibleArtifact(result).artifact;
    if (!nextArtifact) return;
    setArtifact(nextArtifact);
    setSelectedId((current) => nextArtifact.subjects.some((item) => item.id === current) ? current : nextArtifact.subjects[0]?.id ?? '');
  }, [result, sourceResult]);
  if (!artifact) return <section className="stage-run-card character-bible-invalid"><UsersRound size={18} /><div><strong>人物圣经合同未通过</strong><span>{parsed.errors[0] ?? '缺少 CharacterBibleArtifact'}</span></div></section>;
  const updateArtifact = (next: CharacterBibleArtifact) => { setArtifact(next); onArtifactChange(next); };
  const selected = artifact.subjects.find((subject) => subject.id === selectedId) ?? artifact.subjects[0];
  const currentCount = artifact.subjects.filter((item) => item.kind !== 'historical_record').length;
  return (
    <div className="character-bible-workbench">
      <div className="character-bible-statusbar">
        <div><UsersRound size={16} /><span>当下主体</span><strong>{currentCount}</strong></div>
        <div><GitBranch size={16} /><span>关系</span><strong>{artifact.relations.length}</strong></div>
        <div className={readOnly ? 'is-frozen' : 'is-editable'}><LockKeyhole size={16} /><span>{readOnly ? '已冻结' : '当前稿'}</span></div>
      </div>
      {readOnly ? <div className="character-bible-impact"><span>变更影响</span><strong>Volumes</strong><strong>Detail</strong><strong>未完成正文</strong></div> : null}
      <div className="character-bible-viewbar">
        <div aria-label="人物工作台视图" className="character-bible-view-toggle" role="group">
          <button aria-pressed={view === 'star-map'} className={view === 'star-map' ? 'active' : ''} onClick={() => setView('star-map')} type="button"><Orbit size={15} />星图</button>
          <button aria-pressed={view === 'roster'} className={view === 'roster' ? 'active' : ''} onClick={() => setView('roster')} type="button"><List size={15} />名册</button>
        </div>
      </div>
      {selected ? view === 'star-map' ? (
        <div className="character-bible-star-layout">
          <CharacterRosterSection artifact={artifact} onSelect={setSelectedId} selectedId={selected.id} />
          <CharacterStarMapPanel artifact={artifact} onSelect={setSelectedId} selectedId={selected.id} />
          <CharacterDossierEditor artifact={artifact} onChange={updateArtifact} readOnly={readOnly} subject={selected} totalChapters={totalChapters} />
        </div>
      ) : (
        <div className="character-bible-layout">
          <CharacterRosterSection artifact={artifact} onSelect={setSelectedId} selectedId={selected.id} />
          <CharacterDossierEditor artifact={artifact} onChange={updateArtifact} readOnly={readOnly} subject={selected} totalChapters={totalChapters} />
          <CharacterOrchestrationPanel artifact={artifact} onSelect={setSelectedId} subject={selected} />
        </div>
      ) : null}
      <CharacterRelationshipSection artifact={artifact} onChange={updateArtifact} readOnly={readOnly} />
    </div>
  );
}
