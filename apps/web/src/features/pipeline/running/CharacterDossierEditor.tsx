import { Fingerprint } from 'lucide-react';
import { CharacterChapterWindowField } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, CharacterRecord, CharacterTier } from './characterBibleArtifact';

type Props = {
  artifact: CharacterBibleArtifact;
  character: CharacterRecord;
  onChange: (artifact: CharacterBibleArtifact) => void;
  readOnly: boolean;
  totalChapters?: number;
};

const TIER_LABELS: Record<CharacterTier, string> = {
  protagonist: '主角',
  major: '重要配角',
  functional: '功能角色',
};

export function CharacterDossierEditor({ artifact, character, onChange, readOnly, totalChapters }: Props) {
  const update = (patch: Partial<CharacterRecord>) => {
    onChange({
      ...artifact,
      characters: artifact.characters.map((item) => item.id === character.id ? { ...item, ...patch } : item),
    });
  };
  return (
    <section className="character-dossier-editor">
      <header className="character-dossier-heading">
        <div>
          <span>聚焦档案</span>
          <strong>{character.name}</strong>
        </div>
        <div className="character-stable-id"><Fingerprint size={14} /><code>{character.id}</code></div>
      </header>
      <div className="character-identity-grid">
        <label><span>姓名</span><input aria-label="角色姓名" onChange={(event) => update({ name: event.target.value })} readOnly={readOnly} value={character.name} /></label>
        <label>
          <span>角色层级</span>
          <select aria-label="角色层级" disabled={readOnly} onChange={(event) => update({ tier: event.target.value as CharacterTier })} value={character.tier}>
            {Object.entries(TIER_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <CharacterChapterWindowField
          label="首次出现窗口"
          onChange={(first_appearance_window) => update({ first_appearance_window })}
          readOnly={readOnly}
          totalChapters={totalChapters}
          value={character.first_appearance_window}
        />
      </div>
      <div className="character-motive-grid">
        <CharacterField label="叙事职责" onChange={(narrative_function) => update({ narrative_function })} readOnly={readOnly} value={character.narrative_function} />
        <CharacterField label="外在目标" onChange={(external_goal) => update({ external_goal })} readOnly={readOnly} value={character.external_goal} />
        <CharacterField label="内在需要" onChange={(inner_need) => update({ inner_need })} readOnly={readOnly} value={character.inner_need} />
      </div>
      <div className="character-arc-editor">
        <div className="character-arc-label"><span>人物弧</span><strong>起点 / 转折 / 终点</strong></div>
        <div className="character-arc-track" aria-hidden="true"><i /><i /><i /></div>
        <div className="character-arc-fields">
          <CharacterField label="01 起点" onChange={(start) => update({ arc: { ...character.arc, start } })} readOnly={readOnly} value={character.arc.start} />
          <CharacterField label="02 转折" onChange={(turning_point) => update({ arc: { ...character.arc, turning_point } })} readOnly={readOnly} value={character.arc.turning_point} />
          <CharacterField label="03 终点" onChange={(end) => update({ arc: { ...character.arc, end } })} readOnly={readOnly} value={character.arc.end} />
        </div>
      </div>
      <label className="character-boundaries-field">
        <span>不可突破的硬边界</span>
        <textarea
          onChange={(event) => update({ hard_boundaries: splitValues(event.target.value) })}
          placeholder="每行一条；只写后续阶段不得违背的事实"
          readOnly={readOnly}
          rows={3}
          value={character.hard_boundaries.join('\n')}
        />
      </label>
    </section>
  );
}

function CharacterField({ label, onChange, readOnly, value }: { label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) {
  return <label><span>{label}</span><textarea onChange={(event) => onChange(event.target.value)} readOnly={readOnly} rows={3} value={value} /></label>;
}

function splitValues(value: string) {
  return value.split(/[；;\n]/).map((item) => item.trim()).filter(Boolean);
}
