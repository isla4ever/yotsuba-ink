import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { ArtifactRefChips } from './ArtifactRefChips';
import { parseDetailArtifact, type DetailArtifactVnext } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  characters: Array<{ id: string; name: string }>;
  onArtifactChange: (artifact: DetailArtifactVnext) => void;
  readOnly: boolean;
  result: string;
};

export function DetailStageViewVnext({ characters, onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseDetailArtifact(result), [result]);
  const [artifact, setArtifact] = useState<DetailArtifactVnext | null>(parsed.artifact);
  const [selectedRef, setSelectedRef] = useState(parsed.artifact?.chapters[0]?.ref ?? '');
  useEffect(() => {
    if (!parsed.artifact) return;
    setArtifact(parsed.artifact);
    setSelectedRef((current) => parsed.artifact?.chapters.some((chapter) => chapter.ref === current) ? current : parsed.artifact?.chapters[0]?.ref ?? '');
  }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Detail Plan" />;
  const selectedIndex = Math.max(0, artifact.chapters.findIndex((chapter) => chapter.ref === selectedRef));
  const chapter = artifact.chapters[selectedIndex];
  if (!chapter) return <VnextArtifactError errors={['chapters 至少包含一章']} label="Detail Plan" />;
  const update = (next: DetailArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const updateChapter = (patch: Partial<typeof chapter>) => update({
    ...artifact,
    chapters: artifact.chapters.map((item, index) => index === selectedIndex ? { ...item, ...patch } : item),
  });
  return (
    <div className="vnext-artifact-workbench detail-vnext">
      <nav aria-label="章节选择" className="vnext-chapter-nav">
        {artifact.chapters.map((item, index) => (
          <button className={item.ref === chapter.ref ? 'active' : ''} key={item.ref} onClick={() => setSelectedRef(item.ref)} type="button">
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{item.title}</strong>
            <em>{item.volume_ref} · {item.scenes.length} 场景{item.target_characters ? ` · ${item.target_characters.toLocaleString()} 字` : ''}</em>
          </button>
        ))}
      </nav>
      <div className="vnext-detail-main">
        <section className="vnext-artifact-section">
          <header><div><span>章节施工图</span><strong>{chapter.volume_ref} · {chapter.ref}{chapter.target_characters ? ` · ${chapter.target_characters.toLocaleString()} 字` : ''}</strong></div></header>
          <label className="vnext-field vnext-title-field"><span>章名</span><input maxLength={12} minLength={2} onChange={(event) => updateChapter({ title: event.target.value })} readOnly={readOnly} value={chapter.title} /></label>
          <label className="vnext-field vnext-wide"><span>章节目的</span><textarea onChange={(event) => updateChapter({ purpose: event.target.value })} readOnly={readOnly} rows={3} value={chapter.purpose} /></label>
          <div className="vnext-ref-field">
            <span>POV 视角（本章唯一）</span>
            <ArtifactRefChips
              ariaLabel="POV"
              onChange={(ids) => {
                const pov = ids.find((id) => id !== chapter.pov) ?? chapter.pov;
                updateChapter({ pov, cast_ids: includeRef(chapter.cast_ids, pov) });
              }}
              options={characters.map((character) => ({ id: character.id, label: character.name }))}
              readOnly={readOnly}
              selected={[chapter.pov]}
            />
          </div>
          <div className="vnext-ref-field">
            <span>本章出场人物（POV 必含）</span>
            <ArtifactRefChips
              ariaLabel="本章出场人物"
              lockedIds={[chapter.pov]}
              onChange={(cast_ids) => updateChapter({ cast_ids })}
              options={characters.map((character) => ({ id: character.id, label: character.name }))}
              readOnly={readOnly}
              selected={chapter.cast_ids}
            />
          </div>
        </section>
        <section className="vnext-artifact-section">
          <header><div><span>场景序列</span><strong>{chapter.scenes.length} / 4</strong></div>{!readOnly && chapter.scenes.length < 4 ? <button className="vnext-add-command" onClick={() => updateChapter({ scenes: [...chapter.scenes, emptyScene()] })} type="button"><Plus size={15} />新增场景</button> : null}</header>
          <div className="vnext-scene-list">
            {chapter.scenes.map((scene, index) => (
              <article className="vnext-scene-row" key={`${chapter.ref}-scene-${index + 1}`}>
                <div className="vnext-scene-heading"><span>场景 {index + 1}</span><input aria-label="场景地点" onChange={(event) => updateChapter({ scenes: updateItem(chapter.scenes, index, { place: event.target.value }) })} readOnly={readOnly} value={scene.place} />{!readOnly && chapter.scenes.length > 2 ? <button aria-label="删除场景" onClick={() => updateChapter({ scenes: chapter.scenes.filter((_, itemIndex) => itemIndex !== index) })} title="删除场景" type="button"><Trash2 size={15} /></button> : null}</div>
                <div className="vnext-scene-fields">
                  <SceneField label="目标" onChange={(objective) => updateChapter({ scenes: updateItem(chapter.scenes, index, { objective }) })} readOnly={readOnly} value={scene.objective} />
                  <SceneField label="冲突" onChange={(conflict) => updateChapter({ scenes: updateItem(chapter.scenes, index, { conflict }) })} readOnly={readOnly} value={scene.conflict} />
                  <SceneField label="转折" onChange={(turn) => updateChapter({ scenes: updateItem(chapter.scenes, index, { turn }) })} readOnly={readOnly} value={scene.turn} />
                  <SceneField label="结果" onChange={(resultValue) => updateChapter({ scenes: updateItem(chapter.scenes, index, { result: resultValue }) })} readOnly={readOnly} value={scene.result} />
                </div>
              </article>
            ))}
          </div>
        </section>
        <section className="vnext-artifact-section">
          <header><div><span>章节交接</span><strong>下一章只读取这一条交接</strong></div></header>
          <label className="vnext-field vnext-wide"><span>承接压力</span><textarea onChange={(event) => updateChapter({ handoff: event.target.value })} readOnly={readOnly} rows={4} value={chapter.handoff} /></label>
        </section>
      </div>
    </div>
  );
}

function SceneField({ label, onChange, readOnly, value }: { label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) { return <label><span>{label}</span><textarea onChange={(event) => onChange(event.target.value)} readOnly={readOnly} rows={2} value={value} /></label>; }
function updateItem<T>(items: T[], index: number, patch: Partial<T>) { return items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item); }
function includeRef(items: string[], ref: string) { return items.includes(ref) ? items : [...items, ref]; }
function emptyScene(): DetailArtifactVnext['chapters'][number]['scenes'][number] { return { place: '待补充', objective: '待补充', conflict: '待补充', turn: '待补充', result: '待补充' }; }
