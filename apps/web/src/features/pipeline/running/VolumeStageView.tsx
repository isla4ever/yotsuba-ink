import { useEffect, useMemo, useState } from 'react';
import { ArtifactRefChips } from './ArtifactRefChips';
import { parseVolumesArtifact, type VolumeArchitectureArtifact } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type SpineTurn = { id: string; cause: string; change: string };

type Props = {
  characters: Array<{ id: string; name: string }>;
  onArtifactChange: (artifact: VolumeArchitectureArtifact) => void;
  readOnly: boolean;
  result: string;
  spineTurns?: SpineTurn[];
};

const LENGTH_HINTS: Array<{ label: string; hint: string; value: VolumeArchitectureArtifact['volumes'][number]['length_hint'] }> = [
  { label: '短卷', hint: '紧凑收束', value: 'short' },
  { label: '中卷', hint: '标准节奏', value: 'medium' },
  { label: '长卷', hint: '充分展开', value: 'long' },
];

export function VolumeStageView({ characters, onArtifactChange, readOnly, result, spineTurns = [] }: Props) {
  const parsed = useMemo(() => parseVolumesArtifact(result), [result]);
  const [artifact, setArtifact] = useState<VolumeArchitectureArtifact | null>(parsed.artifact);
  const [selectedId, setSelectedId] = useState(parsed.artifact?.volumes[0]?.id ?? '');
  useEffect(() => {
    if (!parsed.artifact) return;
    setArtifact(parsed.artifact);
    setSelectedId((current) => parsed.artifact?.volumes.some((volume) => volume.id === current) ? current : parsed.artifact?.volumes[0]?.id ?? '');
  }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Volume Architecture" />;
  const selectedIndex = Math.max(0, artifact.volumes.findIndex((volume) => volume.id === selectedId));
  const volume = artifact.volumes[selectedIndex];
  if (!volume) return <VnextArtifactError errors={['volumes 至少包含一卷']} label="Volume Architecture" />;
  const update = (next: VolumeArchitectureArtifact) => { setArtifact(next); onArtifactChange(next); };
  const updateVolume = (patch: Partial<typeof volume>) => update({
    ...artifact,
    volumes: artifact.volumes.map((item, index) => index === selectedIndex ? { ...item, ...patch } : item),
  });
  const turnOptions = spineTurns.map((turn, index) => ({ id: turn.id, label: `转折 ${index + 1}`, hint: `${turn.cause} → ${turn.change}` }));
  const castOptions = characters.map((character) => ({ id: character.id, label: character.name }));
  return (
    <div className="vnext-artifact-workbench volumes-vnext">
      <nav aria-label="分卷选择" className="vnext-segmented-nav">
        {artifact.volumes.map((item, index) => <button className={item.id === volume.id ? 'active' : ''} key={item.id} onClick={() => setSelectedId(item.id)} type="button">第 {index + 1} 卷<span>{lengthHintLabel(item.length_hint)}</span></button>)}
      </nav>
      <section className="vnext-artifact-section">
        <header><div><span>完整故事卷</span><strong>{volume.id}</strong></div></header>
        <div className="vnext-field-grid">
          <VolumeField label="本卷承诺" onChange={(promise) => updateVolume({ promise })} readOnly={readOnly} value={volume.promise} />
          <VolumeField label="核心冲突" onChange={(conflict) => updateVolume({ conflict })} readOnly={readOnly} value={volume.conflict} />
          <VolumeField label="高潮" onChange={(climax) => updateVolume({ climax })} readOnly={readOnly} value={volume.climax} />
          <VolumeField label="闭合" onChange={(closure) => updateVolume({ closure })} readOnly={readOnly} value={volume.closure} />
        </div>
      </section>
      <section className="vnext-artifact-section">
        <header><div><span>引用范围</span><strong>只引用冻结的上游事实</strong></div></header>
        {turnOptions.length ? (
          <div className="vnext-ref-field">
            <span>覆盖的 Spine 转折</span>
            <ArtifactRefChips ariaLabel="Spine 转折引用" onChange={(turn_refs) => updateVolume({ turn_refs })} options={turnOptions} readOnly={readOnly} selected={volume.turn_refs} />
          </div>
        ) : (
          <label className="vnext-field"><span>Spine 转折引用</span><textarea onChange={(event) => updateVolume({ turn_refs: splitLines(event.target.value) })} readOnly={readOnly} rows={3} value={volume.turn_refs.join('\n')} /></label>
        )}
        {castOptions.length ? (
          <div className="vnext-ref-field">
            <span>本卷相关人物</span>
            <ArtifactRefChips ariaLabel="本卷相关人物" onChange={(cast_ids) => updateVolume({ cast_ids })} options={castOptions} readOnly={readOnly} selected={volume.cast_ids} />
          </div>
        ) : null}
        <div className="vnext-field-grid">
          <label className="vnext-field"><span>叙事线程引用</span><textarea onChange={(event) => updateVolume({ thread_ids: splitLines(event.target.value) })} readOnly={readOnly} rows={3} value={volume.thread_ids.join('\n')} /></label>
          <div className="vnext-ref-field">
            <span>长度建议（软目标）</span>
            <div aria-label="长度建议" className="vnext-progress-pills" role="group">
              {LENGTH_HINTS.map((option) => (
                <button
                  aria-pressed={volume.length_hint === option.value}
                  className={`vnext-progress-pill${volume.length_hint === option.value ? ' active' : ''}`}
                  disabled={readOnly}
                  key={option.value}
                  onClick={() => updateVolume({ length_hint: option.value })}
                  type="button"
                >
                  <strong>{option.label}</strong>
                  <span>{option.hint}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function VolumeField({ label, onChange, readOnly, value }: { label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) { return <label className="vnext-field"><span>{label}</span><textarea onChange={(event) => onChange(event.target.value)} readOnly={readOnly} rows={4} value={value} /></label>; }
function splitLines(value: string) { return value.split('\n').map((item) => item.trim()).filter(Boolean); }
function lengthHintLabel(value: VolumeArchitectureArtifact['volumes'][number]['length_hint']) { return value === 'short' ? '短卷' : value === 'long' ? '长卷' : '中卷'; }
