import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseSummaryArtifact, type SummaryArtifactVnext } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  characters: Array<{ id: string; name: string }>;
  onArtifactChange: (artifact: SummaryArtifactVnext) => void;
  readOnly: boolean;
  result: string;
};

export function SummaryStageViewVnext({ characters, onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseSummaryArtifact(result), [result]);
  const [artifact, setArtifact] = useState<SummaryArtifactVnext | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Summary Artifact" />;
  const update = (next: SummaryArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const updateBeat = (index: number, patch: Partial<SummaryArtifactVnext['beats'][number]>) => update({ ...artifact, beats: artifact.beats.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) });
  return (
    <div className="vnext-artifact-workbench summary-vnext">
      {parsed.errors.length ? <div className="vnext-contract-warning">{parsed.errors[0]}</div> : null}
      <section className="vnext-artifact-section">
        <header>
          <div><span>故事脊柱</span><strong>{artifact.beats.length} 个因果节拍</strong></div>
          {!readOnly ? <button className="vnext-add-command" onClick={() => update({ ...artifact, beats: [...artifact.beats, { id: nextId('beat', artifact.beats.map((item) => item.id)), phase: '待补充', event: '待补充', consequence: '待补充' }] })} type="button"><Plus size={15} />新增节拍</button> : null}
        </header>
        <div className="vnext-beat-list">
          {artifact.beats.map((beat, index) => (
            <div className="vnext-beat-row" key={beat.id}>
              <span className="vnext-sequence">{String(index + 1).padStart(2, '0')}</span>
              <input aria-label="节拍阶段" onChange={(event) => updateBeat(index, { phase: event.target.value })} readOnly={readOnly} value={beat.phase} />
              <textarea aria-label="节拍事件" onChange={(event) => updateBeat(index, { event: event.target.value })} readOnly={readOnly} rows={2} value={beat.event} />
              <textarea aria-label="节拍后果" onChange={(event) => updateBeat(index, { consequence: event.target.value })} readOnly={readOnly} rows={2} value={beat.consequence} />
              {!readOnly && artifact.beats.length > 1 ? <button aria-label="删除节拍" onClick={() => update({ ...artifact, beats: artifact.beats.filter((_, itemIndex) => itemIndex !== index) })} title="删除节拍" type="button"><Trash2 size={15} /></button> : null}
            </div>
          ))}
        </div>
      </section>
      <section className="vnext-artifact-section vnext-field-grid">
        <label className="vnext-field"><span>高潮</span><textarea onChange={(event) => update({ ...artifact, climax: event.target.value })} readOnly={readOnly} rows={5} value={artifact.climax} /></label>
        <label className="vnext-field"><span>结局</span><textarea onChange={(event) => update({ ...artifact, resolution: event.target.value })} readOnly={readOnly} rows={5} value={artifact.resolution} /></label>
      </section>
      <section className="vnext-artifact-section">
        <header><div><span>人物结局对账</span><strong>{artifact.character_outcomes.length}/{characters.length}</strong></div></header>
        <div className="vnext-outcome-list">
          {characters.map((character) => {
            const outcome = artifact.character_outcomes.find((item) => item.character_id === character.id);
            return (
              <label className="vnext-outcome-row" key={character.id}>
                <strong>{character.name}</strong>
                <textarea
                  onChange={(event) => update({ ...artifact, character_outcomes: upsertOutcome(artifact.character_outcomes, character.id, event.target.value) })}
                  readOnly={readOnly}
                  rows={2}
                  value={outcome?.outcome ?? ''}
                />
              </label>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function upsertOutcome(items: SummaryArtifactVnext['character_outcomes'], characterId: string, outcome: string) {
  const existing = items.some((item) => item.character_id === characterId);
  if (!outcome.trim()) return items.filter((item) => item.character_id !== characterId);
  return existing ? items.map((item) => item.character_id === characterId ? { ...item, outcome } : item) : [...items, { character_id: characterId, outcome }];
}

function nextId(prefix: string, ids: string[]) { let index = ids.length + 1; while (ids.includes(`${prefix}-${index}`)) index += 1; return `${prefix}-${index}`; }
