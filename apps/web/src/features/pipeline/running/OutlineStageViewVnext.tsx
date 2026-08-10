import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseOutlineArtifact, type OutlineArtifactVnext } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  characters: Array<{ id: string; name: string }>;
  onArtifactChange: (artifact: OutlineArtifactVnext) => void;
  readOnly: boolean;
  result: string;
  volumeWindows: string[];
};

export function OutlineStageViewVnext({ characters, onArtifactChange, readOnly, result, volumeWindows }: Props) {
  const parsed = useMemo(() => parseOutlineArtifact(result), [result]);
  const [artifact, setArtifact] = useState<OutlineArtifactVnext | null>(parsed.artifact);
  const [selectedId, setSelectedId] = useState(parsed.artifact?.volumes[0]?.id ?? '');
  useEffect(() => {
    if (!parsed.artifact) return;
    setArtifact(parsed.artifact);
    setSelectedId((current) => parsed.artifact?.volumes.some((volume) => volume.id === current) ? current : parsed.artifact?.volumes[0]?.id ?? '');
  }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Outline Artifact" />;
  const selectedIndex = Math.max(0, artifact.volumes.findIndex((volume) => volume.id === selectedId));
  const volume = artifact.volumes[selectedIndex];
  const update = (next: OutlineArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const updateVolume = (patch: Partial<OutlineArtifactVnext['volumes'][number]>) => update({ ...artifact, volumes: artifact.volumes.map((item, index) => index === selectedIndex ? { ...item, ...patch } : item) });
  if (!volume) return <VnextArtifactError errors={['volumes 至少包含一卷']} label="Outline Artifact" />;
  const projectedWindow = volumeWindows[selectedIndex] ?? volume.chapter_window;
  return (
    <div className="vnext-artifact-workbench outline-vnext">
      <nav aria-label="分卷选择" className="vnext-segmented-nav">
        {artifact.volumes.map((item, index) => <button className={item.id === volume.id ? 'active' : ''} key={item.id} onClick={() => setSelectedId(item.id)} type="button">第 {index + 1} 卷<span>{volumeWindows[index] ?? item.chapter_window}</span></button>)}
      </nav>
      {parsed.errors.length ? <div className="vnext-contract-warning">{parsed.errors[0]}</div> : null}
      <section className="vnext-artifact-section">
        <header><div><span>分卷目标</span><strong>{projectedWindow}</strong></div></header>
        <div className="vnext-field-grid">
          <div className="vnext-field vnext-readonly-projection"><span>冻结章节窗口</span><output>{projectedWindow}</output></div>
          <label className="vnext-field"><span>卷末状态</span><textarea onChange={(event) => updateVolume({ ending_state: event.target.value })} readOnly={readOnly} rows={3} value={volume.ending_state} /></label>
        </div>
        <label className="vnext-field vnext-wide"><span>本卷目标</span><textarea onChange={(event) => updateVolume({ objective: event.target.value })} readOnly={readOnly} rows={4} value={volume.objective} /></label>
      </section>
      <section className="vnext-artifact-section">
        <header>
          <div><span>关键转折</span><strong>{volume.turns.length}</strong></div>
          {!readOnly ? <button className="vnext-add-command" onClick={() => updateVolume({ turns: [...volume.turns, { id: nextId('turn', volume.turns.map((item) => item.id)), event: '待补充', consequence: '待补充' }] })} type="button"><Plus size={15} />新增</button> : null}
        </header>
        <div className="vnext-turn-list">
          {volume.turns.map((turn, index) => (
            <div className="vnext-turn-row" key={turn.id}>
              <span className="vnext-sequence">{index + 1}</span>
              <textarea aria-label="转折事件" onChange={(event) => updateVolume({ turns: updateItem(volume.turns, index, { event: event.target.value }) })} readOnly={readOnly} rows={2} value={turn.event} />
              <textarea aria-label="转折后果" onChange={(event) => updateVolume({ turns: updateItem(volume.turns, index, { consequence: event.target.value }) })} readOnly={readOnly} rows={2} value={turn.consequence} />
              {!readOnly && volume.turns.length > 1 ? <button aria-label="删除转折" onClick={() => updateVolume({ turns: volume.turns.filter((_, itemIndex) => itemIndex !== index), character_windows: volume.character_windows.filter((item) => item.turn_id !== turn.id) })} title="删除转折" type="button"><Trash2 size={15} /></button> : null}
            </div>
          ))}
        </div>
      </section>
      <section className="vnext-artifact-section">
        <header>
          <div><span>人物窗口</span><strong>{volume.character_windows.length}</strong></div>
          {!readOnly && characters.length ? <button className="vnext-add-command" onClick={() => updateVolume({ character_windows: [...volume.character_windows, { character_id: characters[0].id, entry_state: '待补充', exit_state: '待补充', turn_id: volume.turns[0]?.id ?? '' }] })} type="button"><Plus size={15} />新增</button> : null}
        </header>
        <div className="vnext-window-table">
          {volume.character_windows.map((window, index) => (
            <div className="vnext-character-window-row" key={`${window.character_id}-${window.turn_id}-${index}`}>
              <select aria-label="人物" disabled={readOnly} onChange={(event) => updateVolume({ character_windows: updateItem(volume.character_windows, index, { character_id: event.target.value }) })} value={window.character_id}>{characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}</select>
              <select aria-label="关联转折" disabled={readOnly} onChange={(event) => updateVolume({ character_windows: updateItem(volume.character_windows, index, { turn_id: event.target.value }) })} value={window.turn_id}>{volume.turns.map((turn, turnIndex) => <option key={turn.id} value={turn.id}>转折 {turnIndex + 1}</option>)}</select>
              <input aria-label="进入状态" onChange={(event) => updateVolume({ character_windows: updateItem(volume.character_windows, index, { entry_state: event.target.value }) })} readOnly={readOnly} value={window.entry_state} />
              <input aria-label="离开状态" onChange={(event) => updateVolume({ character_windows: updateItem(volume.character_windows, index, { exit_state: event.target.value }) })} readOnly={readOnly} value={window.exit_state} />
              {!readOnly ? <button aria-label="删除人物窗口" onClick={() => updateVolume({ character_windows: volume.character_windows.filter((_, itemIndex) => itemIndex !== index) })} title="删除人物窗口" type="button"><Trash2 size={15} /></button> : null}
            </div>
          ))}
        </div>
      </section>
      <ThreadWindows readOnly={readOnly} updateVolume={updateVolume} volume={volume} />
    </div>
  );
}

function ThreadWindows({ readOnly, updateVolume, volume }: { readOnly: boolean; updateVolume: (patch: Partial<OutlineArtifactVnext['volumes'][number]>) => void; volume: OutlineArtifactVnext['volumes'][number] }) {
  return (
    <section className="vnext-artifact-section">
      <header><div><span>叙事线索窗口</span><strong>{volume.thread_windows.length}</strong></div>{!readOnly ? <button className="vnext-add-command" onClick={() => updateVolume({ thread_windows: [...volume.thread_windows, { thread_id: nextId('thread', volume.thread_windows.map((item) => item.thread_id)), kind: 'plot', action: '待补充', chapter_window: volume.chapter_window }] })} type="button"><Plus size={15} />新增</button> : null}</header>
      <div className="vnext-window-table">
        {volume.thread_windows.map((window, index) => (
          <div className="vnext-thread-window-row" key={`${window.thread_id}-${index}`}>
            <select disabled={readOnly} onChange={(event) => updateVolume({ thread_windows: updateItem(volume.thread_windows, index, { kind: event.target.value as typeof window.kind }) })} value={window.kind}><option value="plot">情节</option><option value="relationship">关系</option><option value="mystery">谜题</option><option value="foreshadow">伏笔</option></select>
            <input aria-label="线索引用" onChange={(event) => updateVolume({ thread_windows: updateItem(volume.thread_windows, index, { thread_id: event.target.value }) })} readOnly={readOnly} value={window.thread_id} />
            <input aria-label="窗口动作" onChange={(event) => updateVolume({ thread_windows: updateItem(volume.thread_windows, index, { action: event.target.value }) })} readOnly={readOnly} value={window.action} />
            <input aria-label="章节窗口" onChange={(event) => updateVolume({ thread_windows: updateItem(volume.thread_windows, index, { chapter_window: event.target.value }) })} readOnly={readOnly} value={window.chapter_window} />
            {!readOnly ? <button aria-label="删除线索窗口" onClick={() => updateVolume({ thread_windows: volume.thread_windows.filter((_, itemIndex) => itemIndex !== index) })} title="删除线索窗口" type="button"><Trash2 size={15} /></button> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function updateItem<T>(items: T[], index: number, patch: Partial<T>) { return items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item); }
function nextId(prefix: string, ids: string[]) { let index = ids.length + 1; while (ids.includes(`${prefix}-${index}`)) index += 1; return `${prefix}-${index}`; }
