import { useEffect, useState } from 'react';
import { BookOpenText, Layers3 } from 'lucide-react';
import type { BookScaleTargetMode, WorkflowStage } from '../contracts';
import {
  bookScaleLimits,
  buildBookScalePlan,
  formatBookChars,
} from '../lib/bookScalePlan';
import { updateStageInputDefault } from '../lib/stageConfig';

type Props = {
  idPrefix: string;
  stage: WorkflowStage;
  onChange: (stage: WorkflowStage) => void;
};

export function BookScaleTargetSection({ idPrefix, stage, onChange }: Props) {
  const mode = scaleMode(stage);
  const rawValue = Number(stage.input_schema.find((field) => field.key === 'book_scale_target_value')?.default);
  const limits = bookScaleLimits[mode];
  const value = Number.isFinite(rawValue) ? rawValue : limits.min;
  const committedPlan = buildBookScalePlan(mode, value);
  const [draftValue, setDraftValue] = useState(String(committedPlan.target_value));
  const draftNumber = Number(draftValue);
  const draftIsValid = Number.isInteger(draftNumber)
    && draftNumber >= limits.min
    && draftNumber <= limits.max;
  const previewPlan = draftIsValid
    ? buildBookScalePlan(mode, draftNumber)
    : committedPlan;

  useEffect(() => {
    setDraftValue(String(committedPlan.target_value));
  }, [mode, committedPlan.target_value]);

  const changeMode = (nextMode: BookScaleTargetMode) => {
    if (nextMode === mode) return;
    const converted = nextMode === 'total_chars'
      ? previewPlan.total_chars
      : previewPlan.total_chapters;
    onChange(updateScale(stage, nextMode, converted));
  };
  const commitDraft = () => {
    const next = Number(draftValue);
    const normalized = Number.isFinite(next) ? next : committedPlan.target_value;
    const updated = buildBookScalePlan(mode, normalized);
    setDraftValue(String(updated.target_value));
    onChange(updateScale(stage, mode, updated.target_value));
  };

  return (
    <section className="book-scale-target" aria-labelledby={`${idPrefix}-book-scale-title`}>
      <div className="book-scale-target-head">
        <div>
          <span>成书体量</span>
          <strong id={`${idPrefix}-book-scale-title`}>选择一个最终目标</strong>
        </div>
        <div className="book-scale-mode" role="group" aria-label="成书目标类型">
          <button
            aria-pressed={mode === 'total_chars'}
            className={mode === 'total_chars' ? 'active' : ''}
            onClick={() => changeMode('total_chars')}
            type="button"
          >
            <BookOpenText aria-hidden="true" size={15} />
            总字数
          </button>
          <button
            aria-pressed={mode === 'total_chapters'}
            className={mode === 'total_chapters' ? 'active' : ''}
            onClick={() => changeMode('total_chapters')}
            type="button"
          >
            <Layers3 aria-hidden="true" size={15} />
            总章数
          </button>
        </div>
      </div>

      <div className="book-scale-target-control">
        <label htmlFor={`${idPrefix}-book-scale-value`}>
          <span>{mode === 'total_chars' ? '计划完成字数' : '计划完成章数'}</span>
          <div>
            <input
              id={`${idPrefix}-book-scale-value`}
              inputMode="numeric"
              max={limits.max}
              min={limits.min}
              step={limits.step}
              type="number"
              value={draftValue}
              onBlur={commitDraft}
              onChange={(event) => setDraftValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  commitDraft();
                }
              }}
            />
            <span>{mode === 'total_chars' ? '字' : '章'}</span>
          </div>
        </label>
        <p>系统按中文可见字符计算，并自动规划卷数、章数和各阶段篇幅。</p>
      </div>

      <dl className="book-scale-preview" aria-label="成书规划预览">
        <div>
          <dt>预计成书</dt>
          <dd>{formatBookChars(previewPlan.total_chars)}</dd>
        </div>
        <div>
          <dt>结构</dt>
          <dd>{previewPlan.volume_count} 卷 / {previewPlan.total_chapters} 章</dd>
        </div>
        <div>
          <dt>单章节奏</dt>
          <dd>{previewPlan.chapter_soft_min_chars.toLocaleString('zh-CN')}-{previewPlan.chapter_soft_max_chars.toLocaleString('zh-CN')} 字</dd>
        </div>
        <div className="book-scale-volume-distribution">
          <dt>各卷章节</dt>
          <dd title={previewPlan.chapters_per_volume.join(' / ')}>{formatDistribution(previewPlan.chapters_per_volume)}</dd>
        </div>
      </dl>
    </section>
  );
}

function scaleMode(stage: WorkflowStage): BookScaleTargetMode {
  const value = stage.input_schema.find((field) => field.key === 'book_scale_target_mode')?.default;
  return value === 'total_chapters' ? 'total_chapters' : 'total_chars';
}

function updateScale(
  stage: WorkflowStage,
  mode: BookScaleTargetMode,
  rawValue: number,
): WorkflowStage {
  const plan = buildBookScalePlan(mode, rawValue);
  return updateStageInputDefault(
    updateStageInputDefault(stage, 'book_scale_target_mode', plan.target_mode),
    'book_scale_target_value',
    plan.target_value,
  );
}

function formatDistribution(distribution: number[]): string {
  if (distribution.length <= 6) return distribution.join(' / ');
  return `${distribution.slice(0, 3).join(' / ')} / ... / ${distribution.slice(-2).join(' / ')}`;
}
