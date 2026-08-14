import { MoveRight, Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseSpineArtifact, type StorySpineArtifact } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  onArtifactChange: (artifact: StorySpineArtifact) => void;
  readOnly: boolean;
  result: string;
};

const PROGRESS_OPTIONS: Array<{ label: string; hint: string; value: StorySpineArtifact['progress_types'][number] }> = [
  { label: '信息推进', hint: '读者知道得更多', value: 'information' },
  { label: '关系推进', hint: '人物之间的位置改变', value: 'relationship' },
  { label: '外部推进', hint: '世界局面被改写', value: 'external' },
  { label: '内部推进', hint: '人物内心被改写', value: 'internal' },
];

export function SpineStageView({ onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseSpineArtifact(result), [result]);
  const [artifact, setArtifact] = useState<StorySpineArtifact | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Story Spine" />;
  const update = (next: StorySpineArtifact) => { setArtifact(next); onArtifactChange(next); };
  const updateTurn = (index: number, patch: Partial<StorySpineArtifact['turns'][number]>) => update({
    ...artifact,
    turns: artifact.turns.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item),
  });
  return (
    <div className="vnext-artifact-workbench spine-vnext">
      <section className="vnext-artifact-section">
        <header>
          <div><span>因果脊柱</span><strong>{artifact.turns.length} 个不可逆变化</strong></div>
          {!readOnly ? <button className="vnext-add-command" onClick={() => update({ ...artifact, turns: [...artifact.turns, { id: `turn-${artifact.turns.length + 1}`, cause: '待补充', change: '待补充' }] })} type="button"><Plus size={15} />新增转折</button> : null}
        </header>
        <div className="vnext-beat-list vnext-spine-chain">
          {artifact.turns.map((turn, index) => (
            <div className="vnext-beat-row" key={turn.id}>
              <span className="vnext-sequence">{String(index + 1).padStart(2, '0')}</span>
              <label className="vnext-beat-cell">
                <span>因为</span>
                <textarea aria-label="转折原因" onChange={(event) => updateTurn(index, { cause: event.target.value })} readOnly={readOnly} rows={2} value={turn.cause} />
              </label>
              <MoveRight aria-hidden="true" className="vnext-beat-arrow" size={16} />
              <label className="vnext-beat-cell">
                <span>局面变成</span>
                <textarea aria-label="局面变化" onChange={(event) => updateTurn(index, { change: event.target.value })} readOnly={readOnly} rows={2} value={turn.change} />
              </label>
              {!readOnly && artifact.turns.length > 1 && index === artifact.turns.length - 1
                ? <button aria-label="删除末尾转折" onClick={() => update({ ...artifact, turns: artifact.turns.slice(0, -1) })} title="删除末尾转折" type="button"><Trash2 size={15} /></button>
                : <span aria-hidden="true" className="vnext-beat-row-spacer" />}
            </div>
          ))}
        </div>
      </section>
      <section className="vnext-artifact-section vnext-field-grid">
        <label className="vnext-field"><span>全书结局</span><textarea onChange={(event) => update({ ...artifact, ending: event.target.value })} readOnly={readOnly} rows={5} value={artifact.ending} /></label>
        <label className="vnext-field"><span>系列开放问题</span><textarea onChange={(event) => update({ ...artifact, open_questions: splitLines(event.target.value) })} readOnly={readOnly} rows={5} value={artifact.open_questions.join('\n')} /></label>
      </section>
      <section className="vnext-artifact-section">
        <header><div><span>推进维度</span><strong>{artifact.progress_types.length} 类推进同时发生</strong></div></header>
        <div aria-label="推进维度" className="vnext-progress-pills" role="group">
          {PROGRESS_OPTIONS.map((option) => {
            const active = artifact.progress_types.includes(option.value);
            return (
              <button
                aria-pressed={active}
                className={`vnext-progress-pill${active ? ' active' : ''}`}
                disabled={readOnly}
                key={option.value}
                onClick={() => update({ ...artifact, progress_types: toggleProgress(artifact.progress_types, option.value) })}
                type="button"
              >
                <strong>{option.label}</strong>
                <span>{option.hint}</span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function splitLines(value: string) { return value.split('\n').map((item) => item.trim()).filter(Boolean); }
function toggleProgress(items: StorySpineArtifact['progress_types'], value: StorySpineArtifact['progress_types'][number]) {
  if (items.includes(value)) return items.length === 1 ? items : items.filter((item) => item !== value);
  return [...items, value];
}
