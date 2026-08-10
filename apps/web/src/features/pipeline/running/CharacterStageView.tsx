import { GitBranch, LockKeyhole, ShieldCheck, UsersRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CharacterNpcSection } from './CharacterNpcSection';
import { CharacterDossierEditor } from './CharacterDossierEditor';
import { CharacterOrchestrationPanel } from './CharacterOrchestrationPanel';
import { CharacterRelationshipSection } from './CharacterRelationshipSection';
import { CharacterRosterSection } from './CharacterRosterSection';
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
  const [selectedId, setSelectedId] = useState(parsed.artifact?.characters[0]?.id ?? '');
  useEffect(() => {
    const next = parseCharacterBibleArtifact(result);
    if (next.artifact) {
      setArtifact(next.artifact);
      setSelectedId((current) => next.artifact?.characters.some((item) => item.id === current) ? current : next.artifact?.characters[0]?.id ?? '');
    }
  }, [result, sourceResult]);
  if (!artifact) {
    return (
      <section className="stage-run-card character-bible-invalid">
        <ShieldCheck size={18} />
        <div><strong>人物圣经合同未通过</strong><span>{parsed.errors[0] ?? '缺少 CharacterBibleArtifact'}</span></div>
      </section>
    );
  }
  const updateArtifact = (next: CharacterBibleArtifact) => {
    setArtifact(next);
    onArtifactChange(next);
  };
  const selected = artifact.characters.find((character) => character.id === selectedId) ?? artifact.characters[0];
  return (
    <div className="character-bible-workbench">
      <div className="character-bible-statusbar">
        <div><UsersRound size={16} /><span>正式角色</span><strong>{artifact.characters.length}</strong></div>
        <div><GitBranch size={16} /><span>关系</span><strong>{artifact.relationships.length}</strong></div>
        <div><ShieldCheck size={16} /><span>NPC 槽位</span><strong>{artifact.npc_slots.length}</strong></div>
        <div className={readOnly ? 'is-frozen' : 'is-editable'}><LockKeyhole size={16} /><span>{readOnly ? '已冻结' : '当前稿'}</span></div>
      </div>
      {readOnly ? (
        <div className="character-bible-impact">
          <span>变更影响</span><strong>Summary</strong><strong>Outline</strong><strong>Detail</strong><strong>未完成正文</strong>
        </div>
      ) : null}
      {parsed.errors.length ? <div className="character-bible-validation">{parsed.errors[0]}</div> : null}
      {selected ? (
        <div className="character-bible-layout">
          <CharacterRosterSection artifact={artifact} onChange={updateArtifact} onSelect={setSelectedId} readOnly={readOnly} selectedId={selected.id} />
          <CharacterDossierEditor artifact={artifact} character={selected} onChange={updateArtifact} readOnly={readOnly} totalChapters={totalChapters} />
          <CharacterOrchestrationPanel artifact={artifact} character={selected} onSelect={setSelectedId} />
        </div>
      ) : null}
      <CharacterRelationshipSection artifact={artifact} onChange={updateArtifact} readOnly={readOnly} />
      <CharacterNpcSection artifact={artifact} onChange={updateArtifact} readOnly={readOnly} totalChapters={totalChapters} />
    </div>
  );
}
