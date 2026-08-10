import { Plus, Trash2 } from 'lucide-react';
import { CharacterChapterWindowField } from './CharacterChapterWindowField';
import type { CharacterBibleArtifact, NpcSlot } from './characterBibleArtifact';
import { nextNpcSlotId } from './characterBibleArtifact';

type Props = {
  artifact: CharacterBibleArtifact;
  onChange: (artifact: CharacterBibleArtifact) => void;
  readOnly: boolean;
  totalChapters?: number;
};

export function CharacterNpcSection({ artifact, onChange, readOnly, totalChapters }: Props) {
  const updateSlot = (id: string, patch: Partial<NpcSlot>) => {
    onChange({ ...artifact, npc_slots: artifact.npc_slots.map((slot) => slot.id === id ? { ...slot, ...patch } : slot) });
  };
  const addSlot = () => {
    onChange({
      ...artifact,
      npc_slots: [...artifact.npc_slots, {
        id: nextNpcSlotId(artifact),
        function: '待补充',
        first_appearance_window: 'chapter:1',
        limits: [],
      }],
    });
  };
  return (
    <section className="character-bible-section character-npc-section">
      <header>
        <div>
          <span>NPC 槽位</span>
          <strong>{artifact.npc_slots.length} 个必要功能位</strong>
        </div>
        {!readOnly ? <button className="character-section-command" onClick={addSlot} type="button"><Plus size={15} />新增槽位</button> : null}
      </header>
      <div className="character-npc-table">
        {artifact.npc_slots.map((slot) => (
          <div className="character-npc-row" key={slot.id}>
            <label><span>叙事功能</span><input onChange={(event) => updateSlot(slot.id, { function: event.target.value })} readOnly={readOnly} value={slot.function} /></label>
            <CharacterChapterWindowField
              label={`${slot.function}首次出现`}
              onChange={(first_appearance_window) => updateSlot(slot.id, { first_appearance_window })}
              readOnly={readOnly}
              totalChapters={totalChapters}
              value={slot.first_appearance_window}
            />
            <label><span>使用限制</span><input onChange={(event) => updateSlot(slot.id, { limits: splitValues(event.target.value) })} readOnly={readOnly} value={slot.limits.join('；')} /></label>
            {!readOnly ? <button aria-label="删除 NPC 槽位" onClick={() => onChange({ ...artifact, npc_slots: artifact.npc_slots.filter((item) => item.id !== slot.id) })} title="删除 NPC 槽位" type="button"><Trash2 size={15} /></button> : null}
          </div>
        ))}
        {!artifact.npc_slots.length ? <p className="character-table-empty">当前不需要额外 NPC 槽位</p> : null}
      </div>
    </section>
  );
}

function splitValues(value: string) {
  return value.split(/[；;\n]/).map((item) => item.trim()).filter(Boolean);
}
