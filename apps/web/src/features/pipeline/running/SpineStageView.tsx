import { MoveRight, Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseSpineArtifact, type SpineMilestone, type StorySpineArtifact } from './artifactsVnext';
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
const MILESTONE_OPTIONS: Array<{ label: string; value: SpineMilestone }> = [
  { label: '启动事件', value: 'inciting' },
  { label: '主动承诺', value: 'commitment' },
  { label: '中心反转', value: 'midpoint_reversal' },
  { label: '策略危机', value: 'crisis' },
  { label: '全书高潮', value: 'climax' },
  { label: '直接余波', value: 'aftermath' },
];

export function SpineStageView({ onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseSpineArtifact(result), [result]);
  const [artifact, setArtifact] = useState<StorySpineArtifact | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Story Spine" />;
  const update = (next: StorySpineArtifact) => {
    const projected = { ...next, progress_types: [...new Set(next.turns.map((turn) => turn.progress_type))] };
    setArtifact(projected);
    onArtifactChange(projected);
  };
  const updateTurn = (index: number, patch: Partial<StorySpineArtifact['turns'][number]>) => update({
    ...artifact,
    turns: artifact.turns.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item),
  });
  return (
    <div className="vnext-artifact-workbench spine-vnext">
      <section className="vnext-artifact-section">
        <header>
          <div><span>因果脊柱</span><strong>{artifact.turns.length} 个不可逆变化</strong></div>
          {!readOnly ? <button className="vnext-add-command" onClick={() => update({ ...artifact, turns: [...artifact.turns, { id: `turn-${artifact.turns.length + 1}`, cause: '待补充', change: '待补充', progress_type: 'external', milestones: [] }] })} type="button"><Plus size={15} />新增转折</button> : null}
        </header>
        <div className="vnext-beat-list vnext-spine-chain">
          {artifact.turns.map((turn, index) => (
            <div className="vnext-beat-row" key={turn.id}>
              <span className="vnext-sequence">{String(index + 1).padStart(2, '0')}</span>
              <label className="vnext-beat-progress">
                <span>推进</span>
                <select aria-label={`转折 ${index + 1} 推进类型`} disabled={readOnly} onChange={(event) => updateTurn(index, { progress_type: event.target.value as StorySpineArtifact['turns'][number]['progress_type'] })} value={turn.progress_type}>
                  {PROGRESS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="vnext-beat-progress">
                <span>结构</span>
                <select aria-label={`转折 ${index + 1} 结构里程碑`} disabled={readOnly} onChange={(event) => updateTurn(index, { milestones: event.target.value ? [event.target.value as SpineMilestone] : [] })} value={turn.milestones[0] ?? ''}>
                  <option value="">常规推进</option>
                  {MILESTONE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                {turn.milestones.length > 1 ? <small>{turn.milestones.map(milestoneLabel).join(' / ')}</small> : null}
              </label>
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
        <div aria-label="推进维度" className="vnext-progress-pills">
          {PROGRESS_OPTIONS.filter((option) => artifact.progress_types.includes(option.value)).map((option) => (
            <div className="vnext-progress-pill active" key={option.value}>
              <strong>{option.label}</strong>
              <span>{option.hint}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function splitLines(value: string) { return value.split('\n').map((item) => item.trim()).filter(Boolean); }
function milestoneLabel(value: SpineMilestone) { return MILESTONE_OPTIONS.find((item) => item.value === value)?.label ?? value; }
