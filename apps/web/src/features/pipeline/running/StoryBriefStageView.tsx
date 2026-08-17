import { useEffect, useMemo, useState } from 'react';
import { suggestScalePlan } from '../lib/narrativeScale';
import { parseStoryBriefArtifact, type StoryBriefArtifact } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = { onArtifactChange: (artifact: StoryBriefArtifact) => void; readOnly: boolean; result: string };

export function StoryBriefStageView({ onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseStoryBriefArtifact(result), [result]);
  const [artifact, setArtifact] = useState<StoryBriefArtifact | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Story Brief" />;
  const scalePlan = suggestScalePlan(artifact.length_envelope);
  const update = (next: StoryBriefArtifact) => { setArtifact(next); onArtifactChange(next); };
  return (
    <div className="vnext-artifact-workbench story-brief-vnext">
      {parsed.errors.length ? <div className="vnext-contract-warning">{parsed.errors[0]}</div> : null}
      <section className="vnext-artifact-section vnext-brief-core">
        <header><span>创作契约</span><strong>全书唯一的承诺来源</strong></header>
        <label className="vnext-field vnext-title-field"><span>书名</span><input onChange={(event) => update({ ...artifact, title: event.target.value })} placeholder="以书名开始这份契约" readOnly={readOnly} value={artifact.title} /></label>
        <label className="vnext-field vnext-wide"><span>故事前提</span><textarea onChange={(event) => update({ ...artifact, premise: event.target.value })} readOnly={readOnly} rows={4} value={artifact.premise} /></label>
        <div className="vnext-field-grid">
          <label className="vnext-field"><span>读者承诺</span><textarea onChange={(event) => update({ ...artifact, promise: event.target.value })} readOnly={readOnly} rows={3} value={artifact.promise} /></label>
          <label className="vnext-field"><span>主题</span><textarea onChange={(event) => update({ ...artifact, theme: event.target.value })} readOnly={readOnly} rows={3} value={artifact.theme} /></label>
          <label className="vnext-field"><span>结局承诺</span><textarea onChange={(event) => update({ ...artifact, ending_promise: event.target.value })} readOnly={readOnly} rows={3} value={artifact.ending_promise} /></label>
        </div>
      </section>
      <section className="vnext-artifact-section">
        <header><span>世界与声音</span><strong>{artifact.world_rules.length} 条世界规则</strong></header>
        <label className="vnext-field vnext-wide"><span>世界规则</span><textarea onChange={(event) => update({ ...artifact, world_rules: splitLines(event.target.value) })} readOnly={readOnly} rows={Math.max(3, artifact.world_rules.length)} value={artifact.world_rules.join('\n')} /></label>
        <label className="vnext-field vnext-wide"><span>叙事声音</span><textarea onChange={(event) => update({ ...artifact, voice: event.target.value })} readOnly={readOnly} rows={3} value={artifact.voice} /></label>
      </section>
      <section className="vnext-artifact-section">
        <header><div><span>长度与结构</span><strong>数量由冻结编辑政策确定</strong></div></header>
        <div className="vnext-field-grid">
          <NumberField label="冻结目标字数" readOnly value={artifact.length_envelope.word_target_soft} />
          <NumberField label="系统章节数" readOnly value={scalePlan.chapterTarget} />
          <NumberField label="系统分卷数" readOnly value={scalePlan.volumeTarget} />
        </div>
      </section>
    </div>
  );
}

function NumberField({ label, readOnly, value }: { label: string; readOnly: boolean; value: number | null }) {
  return <label className="vnext-field"><span>{label}</span><input min={1} readOnly={readOnly} type="number" value={value ?? ''} /></label>;
}

function splitLines(value: string) { return value.split('\n').map((item) => item.trim()).filter(Boolean); }
