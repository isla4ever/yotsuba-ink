import { BookOpenText, SlidersHorizontal, Waypoints } from 'lucide-react';
import type { QualityMode, WorkflowStage } from '../contracts';
import { DEFAULT_CAPACITY_POLICY, lengthEnvelopeFromStage, suggestScalePlan } from '../lib/narrativeScale';
import { updateStageInputDefault, upsertStageInputDefault } from '../lib/stageConfig';

type Props = {
  idPrefix: string;
  stage: WorkflowStage;
  qualityMode?: QualityMode;
  onChange: (stage: WorkflowStage) => void;
};

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
          <strong id={`${idPrefix}-length-envelope-title`}>字数由用户决定，结构数量由系统冻结</strong>
        </div>
      </div>
      <div className="book-scale-preview" aria-label="篇幅软目标">
        <LengthField icon={<BookOpenText aria-hidden="true" size={15} />} id={`${idPrefix}-word-target`} label="目标字数" max={10_000_000} min={1} onChange={(value) => update('word_target_soft', value)} value={envelope.word_target_soft} />
      </div>
      <div className="book-scale-suggestion" aria-label="系统结构建议">
        <SuggestionItem label="章节" value={chapterSuggestionText(plan)} />
        <SuggestionItem label="分卷" value={volumeSuggestionText(plan)} />
        <SuggestionItem label="场景容量" value={sceneRangeText(plan.sceneRange)} />
        <SuggestionItem label="脊柱转折" value={rangeText(plan.turnTarget, plan.turnRange, '个')} />
        <SuggestionItem label="核心人物" value={castRangeText(plan.castRecommendedRange, plan.castHardMax)} />
      </div>
      {qualityMode === 'deep' ? (
        <div className="book-scale-overrides">
          <p className="book-scale-overrides-hint">
            <SlidersHorizontal aria-hidden="true" size={13} />
            精工模式可锁定结构取值；留空表示沿用系统建议区间。
          </p>
          <div className="book-scale-overrides-grid">
            <LengthField
              icon={<Waypoints aria-hidden="true" size={15} />}
              id={`${idPrefix}-turn_target_override`}
              label="锁定脊柱转折数"
              max={Math.min(120, plan.turnRange[1])}
              min={plan.turnRange[0]}
              onChange={(value) => updateOverride('turn_target_override', '锁定脊柱转折数', value)}
              placeholder={`${plan.turnRange[0]}-${plan.turnRange[1]}`}
              value={overrideValue(stage, 'turn_target_override')}
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function chapterSuggestionText(plan: ReturnType<typeof suggestScalePlan>): string {
  const [chapterLow, chapterHigh] = plan.chapterRange;
  const [characterLow, characterHigh] = plan.chapterCharacterRange;
  const chapters = chapterLow === chapterHigh
    ? `${plan.chapterTarget} 章`
    : `系统确定 ${plan.chapterTarget} 章（可行容量 ${chapterLow}-${chapterHigh} 章）`;
  return `${chapters} · 合理章长 ${characterLow.toLocaleString()}-${characterHigh.toLocaleString()} 字`;
}

function volumeSuggestionText(plan: ReturnType<typeof suggestScalePlan>): string {
  const [low, high] = plan.volumeRange;
  const capacity = DEFAULT_CAPACITY_POLICY;
  const range = low === high ? `${low} 卷` : `可行容量 ${low}-${high} 卷`;
  return `系统确定 ${plan.volumeTarget} 卷（${range}） · 单卷 ${capacity.volume_chapters_min}-${capacity.volume_chapters_max} 章`;
}

function rangeText(target: number, [low, high]: [number, number], unit: string): string {
  if (low === high) return `${target} ${unit}`;
  return `建议 ${target} ${unit}（${low}-${high} ${unit}）`;
}

function sceneRangeText([low, high]: [number, number]): string {
  return low === high ? `每章按剧情承载 ${low} 场` : `每章按剧情负载在 ${low}-${high} 场内选择`;
}

function castRangeText([low, high]: [number, number], hardMax: number): string {
  return `按职责生成，建议 ${low}-${high} 人 · 最多 ${hardMax} 人`;
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
