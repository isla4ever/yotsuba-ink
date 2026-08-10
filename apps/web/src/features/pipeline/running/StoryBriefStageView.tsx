import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseStoryBriefArtifact, type StoryBriefArtifact } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = { onArtifactChange: (artifact: StoryBriefArtifact) => void; readOnly: boolean; result: string };

export function StoryBriefStageView({ onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseStoryBriefArtifact(result), [result]);
  const [artifact, setArtifact] = useState<StoryBriefArtifact | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Story Brief" />;
  const update = (next: StoryBriefArtifact) => { setArtifact(next); onArtifactChange(next); };
  return (
    <div className="vnext-artifact-workbench story-brief-vnext">
      {parsed.errors.length ? <div className="vnext-contract-warning">{parsed.errors[0]}</div> : null}
      <section className="vnext-artifact-section vnext-brief-core">
        <header><span>创作契约</span><strong>{artifact.title}</strong></header>
        <label className="vnext-field"><span>书名</span><input onChange={(event) => update({ ...artifact, title: event.target.value })} readOnly={readOnly} value={artifact.title} /></label>
        <label className="vnext-field vnext-wide"><span>故事前提</span><textarea onChange={(event) => update({ ...artifact, premise: event.target.value })} readOnly={readOnly} rows={4} value={artifact.premise} /></label>
        <div className="vnext-field-grid vnext-three">
          <BriefPromiseField label="题材" onChange={(genre) => update({ ...artifact, story_promise: { ...artifact.story_promise, genre } })} readOnly={readOnly} value={artifact.story_promise.genre} />
          <BriefPromiseField label="读者" onChange={(audience) => update({ ...artifact, story_promise: { ...artifact.story_promise, audience } })} readOnly={readOnly} value={artifact.story_promise.audience} />
          <BriefPromiseField label="基调" onChange={(tone) => update({ ...artifact, story_promise: { ...artifact.story_promise, tone } })} readOnly={readOnly} value={artifact.story_promise.tone} />
        </div>
        <div className="vnext-field-grid">
          <label className="vnext-field"><span>主题问题</span><textarea onChange={(event) => update({ ...artifact, thematic_question: event.target.value })} readOnly={readOnly} rows={3} value={artifact.thematic_question} /></label>
          <label className="vnext-field"><span>结局承诺</span><textarea onChange={(event) => update({ ...artifact, ending_promise: event.target.value })} readOnly={readOnly} rows={3} value={artifact.ending_promise} /></label>
        </div>
      </section>
      <section className="vnext-artifact-section">
        <header><span>世界与声音</span><strong>{artifact.world_rules.length} 条世界规则</strong></header>
        <label className="vnext-field vnext-wide"><span>世界规则</span><textarea onChange={(event) => update({ ...artifact, world_rules: splitLines(event.target.value) })} readOnly={readOnly} rows={Math.max(3, artifact.world_rules.length)} value={artifact.world_rules.join('\n')} /></label>
        <div className="vnext-field-grid vnext-three">
          <BriefPromiseField label="视角" onChange={(viewpoint) => update({ ...artifact, voice: { ...artifact.voice, viewpoint } })} readOnly={readOnly} value={artifact.voice.viewpoint} />
          <BriefPromiseField label="时态" onChange={(tense) => update({ ...artifact, voice: { ...artifact.voice, tense } })} readOnly={readOnly} value={artifact.voice.tense} />
          <BriefPromiseField label="质地" onChange={(texture) => update({ ...artifact, voice: { ...artifact.voice, texture } })} readOnly={readOnly} value={artifact.voice.texture} />
        </div>
        <label className="vnext-field vnext-wide"><span>避免项</span><input onChange={(event) => update({ ...artifact, voice: { ...artifact.voice, avoid: splitValues(event.target.value) } })} readOnly={readOnly} value={artifact.voice.avoid.join('；')} /></label>
      </section>
      <section className="vnext-artifact-section">
        <header>
          <div><span>人物需求</span><strong>{artifact.cast_requirements.length} 个职责槽位</strong></div>
          {!readOnly ? <button className="vnext-add-command" onClick={() => update({ ...artifact, cast_requirements: [...artifact.cast_requirements, { function: '待补充', importance: 'functional' }] })} type="button"><Plus size={15} />新增</button> : null}
        </header>
        <div className="vnext-compact-table">
          {artifact.cast_requirements.map((item, index) => (
            <div className="vnext-cast-row" key={`${item.importance}-${index}`}>
              <select disabled={readOnly} onChange={(event) => updateCast(artifact, index, { importance: event.target.value as StoryBriefArtifact['cast_requirements'][number]['importance'] }, update)} value={item.importance}>
                <option value="protagonist">主角</option><option value="major">重要配角</option><option value="functional">功能角色</option><option value="npc">NPC</option>
              </select>
              <input aria-label="人物叙事职责" onChange={(event) => updateCast(artifact, index, { function: event.target.value }, update)} readOnly={readOnly} value={item.function} />
              {!readOnly ? <button aria-label="删除人物需求" onClick={() => update({ ...artifact, cast_requirements: artifact.cast_requirements.filter((_, itemIndex) => itemIndex !== index) })} title="删除人物需求" type="button"><Trash2 size={15} /></button> : null}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function BriefPromiseField({ label, onChange, readOnly, value }: { label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) {
  return <label className="vnext-field"><span>{label}</span><input onChange={(event) => onChange(event.target.value)} readOnly={readOnly} value={value} /></label>;
}

function updateCast(artifact: StoryBriefArtifact, index: number, patch: Partial<StoryBriefArtifact['cast_requirements'][number]>, update: (artifact: StoryBriefArtifact) => void) {
  update({ ...artifact, cast_requirements: artifact.cast_requirements.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) });
}

function splitLines(value: string) { return value.split('\n').map((item) => item.trim()).filter(Boolean); }
function splitValues(value: string) { return value.split(/[；;\n]/).map((item) => item.trim()).filter(Boolean); }
