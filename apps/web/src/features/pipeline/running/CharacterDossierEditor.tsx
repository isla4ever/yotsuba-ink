import { BookOpenText, Fingerprint, IdCard, ShieldCheck, Target, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { CharacterChapterWindowField } from './CharacterChapterWindowField';
import { CharacterKindIcon, characterKindLabels } from './CharacterKindIcon';
import type { CharacterBibleArtifact, CharacterKind, CharacterSubject } from './characterBibleArtifact';

type Props = {
  artifact: CharacterBibleArtifact;
  onChange: (artifact: CharacterBibleArtifact) => void;
  readOnly: boolean;
  subject: CharacterSubject;
  totalChapters?: number;
};

export function CharacterDossierEditor({ artifact, onChange, readOnly, subject, totalChapters }: Props) {
  const update = (patch: Partial<CharacterSubject>) => onChange({
    ...artifact,
    subjects: artifact.subjects.map((item) => item.id === subject.id ? { ...item, ...patch } : item),
  });
  return (
    <section className="character-dossier-editor">
      <header className="character-dossier-heading">
        <div><span>聚焦档案</span><strong><CharacterKindIcon kind={subject.kind} size={15} />{subject.name}</strong></div>
        <div className="character-stable-id"><Fingerprint size={14} /><code>{subject.id}</code></div>
      </header>

      <DossierGroup icon={IdCard} title="身份与登场">
        <div className="character-identity-grid">
          <label><span>姓名</span><input aria-label="主体姓名" onChange={(event) => update({ name: event.target.value })} readOnly={readOnly} value={subject.name} /></label>
          <label><span>主体类型</span><select aria-label="主体类型" disabled={readOnly} onChange={(event) => update({ kind: event.target.value as CharacterKind })} value={subject.kind}>{Object.entries(characterKindLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <CharacterChapterWindowField label="首次出现窗口" onChange={(debut) => update({ debut })} readOnly={readOnly} totalChapters={totalChapters} value={subject.debut} />
        </div>
      </DossierGroup>

      <DossierGroup icon={Target} title="叙事定位">
        <div className="character-dossier-field-grid">
          <CharacterField label="叙事职责" onChange={(value) => update({ function: value })} readOnly={readOnly} value={subject.function} />
          <CharacterField label="行动驱力" onChange={(drive) => update({ drive })} readOnly={readOnly} value={subject.drive} />
          <CharacterField label="当前现实代价" onChange={(present_stakes) => update({ present_stakes })} readOnly={readOnly} value={subject.present_stakes} />
          <CharacterField label="必要变化" onChange={(change) => update({ change })} readOnly={readOnly} value={subject.change} />
        </div>
      </DossierGroup>

      <DossierGroup icon={BookOpenText} title="前史与人物质地">
        <div className="character-dossier-field-grid">
          <CharacterField className="wide" label="既往身份与经历" onChange={(background) => update({ background })} readOnly={readOnly} rows={4} value={subject.background} />
          <CharacterField className="wide" label="与主线的既往渊源" onChange={(conflict_history) => update({ conflict_history })} readOnly={readOnly} rows={4} value={subject.conflict_history} />
          <CharacterField label="性格与行为" onChange={(temperament) => update({ temperament })} readOnly={readOnly} value={subject.temperament} />
          <CharacterField label="语言习惯" onChange={(speech_style) => update({ speech_style })} readOnly={readOnly} value={subject.speech_style} />
        </div>
      </DossierGroup>

      <DossierGroup icon={ShieldCheck} title="写作护栏">
        <div className="character-dossier-field-grid">
          <label className="character-boundaries-field"><span>使用限制</span><textarea onChange={(event) => update({ limits: splitValues(event.target.value) })} readOnly={readOnly} rows={5} value={subject.limits.join('\n')} /></label>
          <label className="character-boundaries-field"><span>职责需求引用</span><textarea onChange={(event) => update({ demand_refs: splitValues(event.target.value) })} readOnly={readOnly} rows={5} value={subject.demand_refs.join('\n')} /></label>
        </div>
      </DossierGroup>
    </section>
  );
}

function DossierGroup({ children, icon: Icon, title }: { children: ReactNode; icon: LucideIcon; title: string }) {
  return <section className="character-dossier-group"><header><Icon aria-hidden="true" size={15} /><strong>{title}</strong></header>{children}</section>;
}

function CharacterField({ className = '', label, onChange, readOnly, rows = 3, value }: { className?: string; label: string; onChange: (value: string) => void; readOnly: boolean; rows?: number; value: string }) {
  return <label className={className}><span>{label}</span><textarea onChange={(event) => onChange(event.target.value)} readOnly={readOnly} rows={rows} value={value} /></label>;
}

function splitValues(value: string) {
  return value.split(/[；;\n]/).map((item) => item.trim()).filter(Boolean);
}
