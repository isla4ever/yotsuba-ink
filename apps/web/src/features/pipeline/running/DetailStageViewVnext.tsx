import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseDetailArtifact, type DetailArtifactVnext } from './artifactsVnext';
import type { DetailObligationKind, DetailObligationOption } from './detailObligationRegistry';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  characters: Array<{ id: string; name: string }>;
  obligationOptions: DetailObligationOption[];
  onArtifactChange: (artifact: DetailArtifactVnext) => void;
  readOnly: boolean;
  result: string;
};

export function DetailStageViewVnext({ characters, obligationOptions, onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseDetailArtifact(result), [result]);
  const [artifact, setArtifact] = useState<DetailArtifactVnext | null>(parsed.artifact);
  const [selectedId, setSelectedId] = useState(parsed.artifact?.chapters[0]?.id ?? '');
  useEffect(() => {
    if (!parsed.artifact) return;
    setArtifact(parsed.artifact);
    setSelectedId((current) => parsed.artifact?.chapters.some((chapter) => chapter.id === current) ? current : parsed.artifact?.chapters[0]?.id ?? '');
  }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Detail Artifact" />;
  const selectedIndex = Math.max(0, artifact.chapters.findIndex((chapter) => chapter.id === selectedId));
  const chapter = artifact.chapters[selectedIndex];
  const update = (next: DetailArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const updateChapter = (patch: Partial<DetailArtifactVnext['chapters'][number]>) => update({ ...artifact, chapters: artifact.chapters.map((item, index) => index === selectedIndex ? { ...item, ...patch } : item) });
  if (!chapter) return <VnextArtifactError errors={['chapters 至少包含一章']} label="Detail Artifact" />;
  return (
    <div className="vnext-artifact-workbench detail-vnext">
      <nav aria-label="章节选择" className="vnext-chapter-nav">
        {artifact.chapters.map((item) => <button className={item.id === chapter.id ? 'active' : ''} key={item.id} onClick={() => setSelectedId(item.id)} type="button"><span>{String(item.number).padStart(2, '0')}</span><strong>{item.purpose}</strong></button>)}
      </nav>
      <div className="vnext-detail-main">
        {parsed.errors.length ? <div className="vnext-contract-warning">{parsed.errors[0]}</div> : null}
        <section className="vnext-artifact-section">
          <header><div><span>第 {chapter.number} 章</span><strong>{chapter.id}</strong></div></header>
          <div className="vnext-field-grid">
            <label className="vnext-field"><span>章节目的</span><textarea onChange={(event) => updateChapter({ purpose: event.target.value })} readOnly={readOnly} rows={3} value={chapter.purpose} /></label>
            <label className="vnext-field"><span>POV</span><select disabled={readOnly} onChange={(event) => updateChapter({ pov_character_id: event.target.value })} value={chapter.pov_character_id}>{characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}</select></label>
          </div>
        </section>
        <section className="vnext-artifact-section">
          <header><div><span>场景施工</span><strong>{chapter.scenes.length}/3</strong></div>{!readOnly && chapter.scenes.length < 3 ? <button className="vnext-add-command" onClick={() => updateChapter({ scenes: [...chapter.scenes, { id: nextId('scene', chapter.scenes.map((item) => item.id)), location: '待补充', goal: '待补充', obstacle: '待补充', turn: '待补充', outcome: '待补充' }] })} type="button"><Plus size={15} />新增场景</button> : null}</header>
          <div className="vnext-scene-list">
            {chapter.scenes.map((scene, index) => (
              <article className="vnext-scene-row" key={scene.id}>
                <div className="vnext-scene-heading"><span>场景 {index + 1}</span><input aria-label="场景地点" onChange={(event) => updateChapter({ scenes: updateItem(chapter.scenes, index, { location: event.target.value }) })} readOnly={readOnly} value={scene.location} />{!readOnly && chapter.scenes.length > 1 ? <button aria-label="删除场景" onClick={() => updateChapter({ scenes: chapter.scenes.filter((_, itemIndex) => itemIndex !== index) })} title="删除场景" type="button"><Trash2 size={15} /></button> : null}</div>
                <div className="vnext-scene-fields">
                  <SceneField label="目标" onChange={(goal) => updateChapter({ scenes: updateItem(chapter.scenes, index, { goal }) })} readOnly={readOnly} value={scene.goal} />
                  <SceneField label="阻碍" onChange={(obstacle) => updateChapter({ scenes: updateItem(chapter.scenes, index, { obstacle }) })} readOnly={readOnly} value={scene.obstacle} />
                  <SceneField label="转折" onChange={(turn) => updateChapter({ scenes: updateItem(chapter.scenes, index, { turn }) })} readOnly={readOnly} value={scene.turn} />
                  <SceneField label="结果" onChange={(outcome) => updateChapter({ scenes: updateItem(chapter.scenes, index, { outcome }) })} readOnly={readOnly} value={scene.outcome} />
                </div>
              </article>
            ))}
          </div>
        </section>
        <ObligationSection chapter={chapter} obligationOptions={obligationOptions} readOnly={readOnly} updateChapter={updateChapter} />
        <section className="vnext-artifact-section">
          <header><div><span>章节交接</span><strong>传递给第 {chapter.number + 1} 章</strong></div></header>
          <div className="vnext-field-grid vnext-three">
            <label className="vnext-field"><span>未完成动作</span><textarea onChange={(event) => updateChapter({ handoff: { ...chapter.handoff, unresolved_actions: splitLines(event.target.value) } })} readOnly={readOnly} rows={3} value={chapter.handoff.unresolved_actions.join('\n')} /></label>
            <label className="vnext-field"><span>情绪承接</span><textarea onChange={(event) => updateChapter({ handoff: { ...chapter.handoff, emotional_carryover: splitLines(event.target.value) } })} readOnly={readOnly} rows={3} value={chapter.handoff.emotional_carryover.join('\n')} /></label>
            <label className="vnext-field"><span>下一压力</span><textarea onChange={(event) => updateChapter({ handoff: { ...chapter.handoff, next_pressure: event.target.value } })} readOnly={readOnly} rows={3} value={chapter.handoff.next_pressure} /></label>
          </div>
        </section>
      </div>
    </div>
  );
}

function ObligationSection({ chapter, obligationOptions, readOnly, updateChapter }: { chapter: DetailArtifactVnext['chapters'][number]; obligationOptions: DetailObligationOption[]; readOnly: boolean; updateChapter: (patch: Partial<DetailArtifactVnext['chapters'][number]>) => void }) {
  const initial = obligationOptions.find((item) => item.kind === 'thread') ?? obligationOptions[0];
  return (
    <section className="vnext-artifact-section">
      <header><div><span>本章义务</span><strong>{chapter.obligations.length}</strong></div>{!readOnly ? <button className="vnext-add-command" disabled={!initial} onClick={() => initial && updateChapter({ obligations: [...chapter.obligations, { kind: initial.kind, ref_id: initial.id, action: '待补充' }] })} type="button"><Plus size={15} />新增义务</button> : null}</header>
      <div className="vnext-obligation-list">
        {chapter.obligations.map((obligation, index) => {
          const options = obligationOptions.filter((item) => item.kind === obligation.kind);
          return (
          <div className="vnext-obligation-row" key={`${obligation.kind}-${obligation.ref_id}-${index}`}>
            <select aria-label="义务类型" disabled={readOnly} onChange={(event) => {
              const kind = event.target.value as DetailObligationKind;
              const next = obligationOptions.find((item) => item.kind === kind);
              updateChapter({ obligations: updateItem(chapter.obligations, index, { kind, ref_id: next?.id ?? '' }) });
            }} value={obligation.kind}><option value="character">人物</option><option value="thread">线索</option><option value="world_rule">世界规则</option><option value="promise">叙事承诺</option></select>
            <select aria-label="义务引用" disabled={readOnly || !options.length} onChange={(event) => updateChapter({ obligations: updateItem(chapter.obligations, index, { ref_id: event.target.value }) })} value={obligation.ref_id}>
              {!options.some((item) => item.id === obligation.ref_id) ? <option value={obligation.ref_id}>未登记引用</option> : null}
              {options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
            <input aria-label="义务动作" onChange={(event) => updateChapter({ obligations: updateItem(chapter.obligations, index, { action: event.target.value }) })} readOnly={readOnly} value={obligation.action} />
            {!readOnly ? <button aria-label="删除义务" onClick={() => updateChapter({ obligations: chapter.obligations.filter((_, itemIndex) => itemIndex !== index) })} title="删除义务" type="button"><Trash2 size={15} /></button> : null}
          </div>
        );})}
      </div>
    </section>
  );
}

function SceneField({ label, onChange, readOnly, value }: { label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) { return <label><span>{label}</span><textarea onChange={(event) => onChange(event.target.value)} readOnly={readOnly} rows={2} value={value} /></label>; }
function updateItem<T>(items: T[], index: number, patch: Partial<T>) { return items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item); }
function nextId(prefix: string, ids: string[]) { let index = ids.length + 1; while (ids.includes(`${prefix}-${index}`)) index += 1; return `${prefix}-${index}`; }
function splitLines(value: string) { return value.split('\n').map((item) => item.trim()).filter(Boolean); }
