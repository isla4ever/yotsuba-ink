import { BookOpenText, Layers, ListOrdered, SlidersHorizontal, Users, Waypoints } from 'lucide-react';
import type { QualityMode, WorkflowStage } from '../contracts';
import { lengthEnvelopeFromStage, suggestScalePlan } from '../lib/narrativeScale';
import { updateStageInputDefault, upsertStageInputDefault } from '../lib/stageConfig';

type Props = {
  idPrefix: string;
  stage: WorkflowStage;
  qualityMode?: QualityMode;
  onChange: (stage: WorkflowStage) => void;
};

const OVERRIDE_FIELDS = [
  { key: 'volume_target_override', label: '自定义卷数', icon: Layers, min: 1, max: 50 },
  { key: 'turn_target_override', label: '自定义脊柱转折数', icon: Waypoints, min: 3, max: 24 },
  { key: 'cast_demand_override', label: '自定义人物数量', icon: Users, min: 1, max: 30 },
] as const;

export function LengthEnvelopeSection({ idPrefix, stage, qualityMode = 'balanced', onChange }: Props) {
  const envelope = lengthEnvelopeFromStage(stage);
  const plan = suggestScalePlan(envelope);
  const update = (key: string, value: number | null) => onChange(updateStageInputDefault(stage, key, value));
  const updateOverride = (key: string, label: string, value: number | null) =>
    onChange(upsertStageInputDefault(stage, key, label, value));
  return (
    <section className="book-scale-target" aria-labelledby={`${idPrefix}-length-envelope-title`}>
      <div className="book-scale-target-head">
        <div>
          <span>篇幅包络</span>
          <strong id={`${idPrefix}-length-envelope-title`}>软目标，不锁定故事边界</strong>
        </div>
      </div>
      <div className="book-scale-preview" aria-label="篇幅软目标">
        <LengthField icon={<BookOpenText aria-hidden="true" size={15} />} id={`${idPrefix}-word-target`} label="目标字数" max={10_000_000} min={1} onChange={(value) => update('word_target_soft', value)} value={envelope.word_target_soft} />
        <LengthField icon={<ListOrdered aria-hidden="true" size={15} />} id={`${idPrefix}-chapter-target`} label="建议章数" max={10_000} min={1} onChange={(value) => update('chapter_target_soft', value)} placeholder="留空则按字数估算" value={envelope.chapter_target_soft} />
      </div>
      <div className="book-scale-suggestion" aria-label="系统结构建议">
        <SuggestionItem label="章节" value={`约 ${plan.chapterTarget} 章${plan.wordsPerChapter ? ` · 每章约 ${plan.wordsPerChapter.toLocaleString()} 字` : ''}`} />
        <SuggestionItem label="分卷" value={rangeText(plan.volumeTarget, plan.volumeRange, '卷')} />
        <SuggestionItem label="脊柱转折" value={rangeText(plan.turnTarget, plan.turnRange, '个')} />
        <SuggestionItem label="登场人物" value={rangeText(plan.castTarget, plan.castRange, '人')} />
      </div>
      {qualityMode === 'deep' ? (
        <div className="book-scale-overrides">
          <p className="book-scale-overrides-hint">
            <SlidersHorizontal aria-hidden="true" size={13} />
            精工模式可锁定结构取值；留空表示沿用系统建议区间。
          </p>
          <div className="book-scale-overrides-grid">
            {OVERRIDE_FIELDS.map(({ key, label, icon: Icon, min, max }) => (
              <LengthField
                icon={<Icon aria-hidden="true" size={15} />}
                id={`${idPrefix}-${key}`}
                key={key}
                label={label}
                max={max}
                min={min}
                onChange={(value) => updateOverride(key, label, value)}
                placeholder="留空用建议值"
                value={overrideValue(stage, key)}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function rangeText(target: number, [low, high]: [number, number], unit: string): string {
  if (low === high) return `${target} ${unit}`;
  return `建议 ${target} ${unit}（${low}-${high} ${unit}）`;
}

function overrideValue(stage: WorkflowStage, key: string): number | null {
  const raw = stage.input_schema.find((field) => field.key === key)?.default;
  const numeric = Number(raw);
  return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
}

function SuggestionItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="book-scale-suggestion-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LengthField({ icon, id, label, max, min, onChange, placeholder, value }: { icon?: React.ReactNode; id: string; label: string; max: number; min: number; onChange: (value: number | null) => void; placeholder?: string; value: number | null }) {
  return (
    <label htmlFor={id}>
      <span>{icon}{label}</span>
      <input id={id} max={max} min={min} onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)} placeholder={placeholder} step="1" type="number" value={value ?? ''} />
    </label>
  );
}
